#
# This program is largely based on the TelemFFB distribution (https://github.com/walmis/TelemFFB).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#

"""
JoystickManager Module

This module is responsible for communicating with the force feedback joystick,
including sending effects and reading axis positions.
"""

import logging
import hid
import time
import ctypes
from threading import Thread, Lock, Event

# --- FFB Report Structures from ffb_rhino.py ---
HID_REPORT_ID_SET_EFFECT = 101
HID_REPORT_ID_EFFECT_OPERATION = 110
HID_REPORT_ID_SET_CONSTANT_FORCE = 105
HID_REPORT_ID_SET_PERIODIC = 104
HID_REPORT_ID_SET_CONDITION = 103

EFFECT_CONSTANT = 1
EFFECT_SINE = 4
EFFECT_SQUARE = 3

# --- Additional Effect Types for symmetrical vibration ---
EFFECT_SAWTOOTHUP = 6
EFFECT_SAWTOOTHDOWN = 7

OP_START = 1
AXIS_ENABLE_DIR = 4
AXIS_ENABLE_X = 1
AXIS_ENABLE_Y = 2

class FFBReport_SetEffect(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [("reportId", ctypes.c_uint8), ("effectBlockIndex", ctypes.c_uint8),
                ("effectType", ctypes.c_uint8), ("duration", ctypes.c_uint16),
                ("triggerRepeatInterval", ctypes.c_uint16), ("samplePeriod", ctypes.c_uint16),
                ("gain", ctypes.c_uint16), ("triggerButton", ctypes.c_uint8),
                ("axesEnable", ctypes.c_uint8), ("directionX", ctypes.c_uint8),
                ("directionY", ctypes.c_uint8), ("startDelay", ctypes.c_uint16)]
    def __init__(self, **kwargs): super().__init__(**{**{"reportId": HID_REPORT_ID_SET_EFFECT, "gain": 4096}, **kwargs})

class FFBReport_EffectOperation(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [("reportId", ctypes.c_uint8), ("effectBlockIndex", ctypes.c_uint8),
                ("operation", ctypes.c_uint8), ("loopCount", ctypes.c_uint8)]
    def __init__(self, **kwargs): super().__init__(**{"reportId": HID_REPORT_ID_EFFECT_OPERATION}, **kwargs)

class FFBReport_SetConstantForce(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [("reportId", ctypes.c_uint8), ("effectBlockIndex", ctypes.c_uint8),
                ("magnitude", ctypes.c_int16)]
    def __init__(self, **kwargs): super().__init__(**{"reportId": HID_REPORT_ID_SET_CONSTANT_FORCE}, **kwargs)

class FFBReport_SetPeriodic(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [("reportId", ctypes.c_uint8), ("effectBlockIndex", ctypes.c_uint8),
                ("magnitude", ctypes.c_uint16), ("offset", ctypes.c_int16),
                ("phase", ctypes.c_uint8), ("period", ctypes.c_uint16)]
    def __init__(self, **kwargs): super().__init__(**{"reportId": HID_REPORT_ID_SET_PERIODIC}, **kwargs)

class FFBReport_SetCondition(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
        ("reportId", ctypes.c_uint8),
        ("effectBlockIndex", ctypes.c_uint8), 
        ("parameterBlockOffset", ctypes.c_uint8), 
        ("cpOffset", ctypes.c_int16), 
        ("positiveCoefficient", ctypes.c_int16), 
        ("negativeCoefficient", ctypes.c_int16), 
        ("positiveSaturation", ctypes.c_uint16), 
        ("negativeSaturation", ctypes.c_uint16), 
        ("deadBand", ctypes.c_uint16)
    ]
    _defaults_ = { "reportId": HID_REPORT_ID_SET_CONDITION }

    def __init__(self, **kwargs):
        values = type(self)._defaults_.copy()
        values.update(kwargs)
        super().__init__(**values)

class JoystickManager(Thread):
    """Manages communication with a VPforce Rhino FFB joystick."""

    def __init__(self, vendor_id=0xFFFF, product_id=0x2055):
        super().__init__(daemon=True)
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.device = None
        self.is_connected = False
        self.axes = {'jx': 0.0, 'jy': 0.0}
        # --- vibration management state ---
        # key -> state dict containing slot / pending / last_props
        self._periodic_states = {}
        self._used_slots = set()
        # Condition effect state (damper / inertia / friction)
        self._condition_states = {}
        self.lock = Lock()
        self._quit_event = Event()
        
        self.start()

    def _connect_to_device(self):
        """Finds and connects to the specified joystick device using HID usage page."""
        if self.is_connected:
            return True
            
        logging.info(f"Searching for joystick with VID=0x{self.vendor_id:04x}, PID=0x{self.product_id:04x}")
        
        try:
            # Enumerate all HID devices that match the VID/PID
            all_devices = hid.enumerate(self.vendor_id, self.product_id)
            
            # Filter for the correct interface (joystick on interface 0, usage page 1, usage 4)
            joystick_devices = [
                dev for dev in all_devices
                if dev['interface_number'] == 0 and dev['usage_page'] == 1 and dev['usage'] == 4
            ]

            if not joystick_devices:
                raise IOError("No matching joystick HID interface found. (Looking for Usage Page 1, Usage 4)")
            
            path = joystick_devices[0]['path']
            self.device = hid.device()
            self.device.open_path(path)
            self.device.set_nonblocking(1) # Set device to non-blocking mode
            self.is_connected = True
            logging.info(f"Successfully connected to joystick: {self.device.get_product_string()}")
            return True

        except (IOError, AttributeError, ValueError) as e:
            logging.error(f"Could not connect to joystick: {e}")
            if self.device:
                self.device.close()
            self.device = None
            self.is_connected = False
            return False
            
    def run(self):
        """Threaded loop to continuously read axis data."""
        while not self._quit_event.is_set():
            if not self.is_connected:
                if self._connect_to_device():
                    # If connection is successful, proceed to read data
                    pass
                else:
                    # If connection fails, wait 10 seconds before retrying
                    self._quit_event.wait(10)
                    continue

            try:
                # Read data from the device. Now non-blocking.
                report = self.device.read(64) 
                if report:
                    self._parse_input_report(report)
            except (IOError, ValueError) as e:
                logging.error(f"Error reading from joystick, disconnecting: {e}")
                self.is_connected = False
                if self.device:
                    self.device.close()
                self.device = None
            
            time.sleep(0.001)

    def _parse_input_report(self, report):
        """Parses the HID input report to extract axis data for VPforce Rhino."""
        with self.lock:
            # Report format for VPforce Rhino: Report ID 1, X/Y are 16-bit signed
            if report[0] == 1:
                raw_x = (report[2] << 8) | report[1]
                raw_y = (report[4] << 8) | report[3]
                
                # Convert from 0-65535 range to -32768 to 32767
                x_signed = raw_x if raw_x < 32768 else raw_x - 65536
                y_signed = raw_y if raw_y < 32768 else raw_y - 65536

                # Scale to -1.0 to 1.0 based on a typical range (e.g., +/- 4096)
                # This might need adjustment based on device calibration
                self.axes['jx'] = x_signed / 4096.0
                self.axes['jy'] = y_signed / 4096.0

    def apply_effects(self, effects):
        if not self.is_connected:
            return

        # Handle *all* periodic vibration effects generically
        self._update_periodic_effects(effects)

        # Handle damper / inertia / friction condition effects
        self._update_condition_effects(effects)

        if 'constant_force' in effects:
            self._send_constant_force_effect(effects['constant_force'])
        else:
            self.stop_effect(2) # Stop constant force effect if not present

        # Springs are always sent
        self._send_spring_effect(axis=0, props=effects.get('spring_x', {'coefficient': 0, 'cp_offset': 0}))
        self._send_spring_effect(axis=1, props=effects.get('spring_y', {'coefficient': 0, 'cp_offset': 0}))

    def _send_constant_force_effect(self, props):
        """Constructs and sends a constant force effect."""
        effect_id = 2 # Use slot 2 for constant force
        magnitude = int(props.get('magnitude', 0) * 4096)
        
        # --- Axis Correction ---
        # The joystick hardware appears to have a reflected coordinate system for forces.
        # We correct this by transforming the angle: new_angle = 90 - old_angle.
        original_direction = props.get('direction', 0)
        corrected_direction = (90 - original_direction) % 360
        direction_hid = int(corrected_direction * 255 / 360)

        # 1. Set the basic effect type and direction
        set_effect_report = FFBReport_SetEffect(
            effectBlockIndex=effect_id, effectType=EFFECT_CONSTANT,
            axesEnable=AXIS_ENABLE_DIR, directionX=direction_hid
        )
        self._write_report(bytes(set_effect_report))

        # 2. Set the magnitude
        set_force_report = FFBReport_SetConstantForce(
            effectBlockIndex=effect_id, magnitude=magnitude
        )
        self._write_report(bytes(set_force_report))

        # 3. Start the effect
        self.start_effect(effect_id)

    # ------------------------------------------------------------------
    # Multi-vibration support (generic periodic effects)
    # ------------------------------------------------------------------

    def _allocate_dynamic_slot(self):
        """Return a free effect slot id, skipping slots used by condition effects (9-11)."""
        # Try slots 3-8 first (below condition effects)
        for eid in range(3, 9): # 3-8
            if eid not in self._used_slots:
                self._used_slots.add(eid)
                return eid
        # Then try slots 12-23 (above condition effects)
        for eid in range(12, 24): # 12-23
            if eid not in self._used_slots:
                self._used_slots.add(eid)
                return eid
        return None

    def _release_dynamic_slot(self, slot):
        self._used_slots.discard(slot)

    def _update_periodic_effects(self, effects_dict):
        """Ensure all requested periodic vibration effects are running and update/stop as required."""

        # Collect requested vibration effects (stick_shaker, runway_rumble, + any future ones that declare 'frequency')
        requested = {
            name: props for name, props in effects_dict.items()
            if isinstance(props, dict) and 'frequency' in props
        }

        # Stop effects that are no longer requested
        for name in list(self._periodic_states.keys()):
            if name not in requested:
                state = self._periodic_states.pop(name)
                self.stop_effect(state['slot'])
                self._release_dynamic_slot(state['slot'])

        # Update or start requested effects
        for name, props in requested.items():
            state = self._periodic_states.get(name)

            # --- common calculations ---
            target_mag = int(props.get('magnitude', 0) * 4096)
            freq = props.get('frequency', 0)
            period = int(1000 / freq) if freq > 0 else 0

            waveform = props.get('waveform', 'sine')
            if waveform == 'square':
                et_type = EFFECT_SQUARE  # device interprets as square
            elif waveform == 'sine':
                et_type = EFFECT_SINE
            elif waveform == 'saw_up':
                et_type = EFFECT_SAWTOOTHUP
            elif waveform == 'saw_down':
                et_type = EFFECT_SAWTOOTHDOWN
            else:
                et_type = EFFECT_SINE

            # Axis correction
            orig_dir = props.get('direction', 0)
            corr_dir = (90 - orig_dir) % 360
            dir_hid = int(corr_dir * 255 / 360)

            def _configure(effect_id, effect_type, dir_val, mag):
                # 1. Header
                self._write_report(bytes(FFBReport_SetEffect(
                    effectBlockIndex=effect_id, effectType=effect_type,
                    axesEnable=AXIS_ENABLE_DIR, directionX=dir_val)))

                # 2. Periodic params
                self._write_report(bytes(FFBReport_SetPeriodic(
                    effectBlockIndex=effect_id, magnitude=mag,
                    period=period, phase=0)))

            if state is None:
                slot = self._allocate_dynamic_slot()
                if slot is None:
                    logging.warning("No free vibration slots – skipping effect '%s'" % name)
                    continue

                # Configure with zero magnitude and start immediately
                _configure(slot, et_type, dir_hid, 0)
                self.start_effect(slot)

                self._periodic_states[name] = {
                    'slot': slot,
                    'pending': True,  # will get real magnitude on the next tick
                    'props': props.copy()
                }
                continue

            slot = state['slot']

            # Apply real magnitude on the next tick
            if state.get('pending'):
                _configure(slot, et_type, dir_hid, target_mag)
                state['pending'] = False
                state['props'] = props.copy()
                continue

            # Property change?
            if props != state.get('props'):
                _configure(slot, et_type, dir_hid, target_mag)
                state['props'] = props.copy()

    # ------------------------------------------------------------------
    # Condition effects (Damper, Inertia, Friction)
    # ------------------------------------------------------------------

    _COND_TYPE_MAP = {
        'damper': 9,      # EFFECT_DAMPER
        'inertia': 10,    # EFFECT_INERTIA
        'friction': 11    # EFFECT_FRICTION
    }

    def _update_condition_effects(self, effects_dict):
        requested = {
            k: v for k, v in effects_dict.items() if k in self._COND_TYPE_MAP
        }

        # stop removed
        for name in list(self._condition_states.keys()):
            if name not in requested:
                state = self._condition_states.pop(name)
                slot = state['slot']
                self.stop_effect(slot)
                self._used_slots.discard(slot)

        # update/start
        for name, props in requested.items():
            effect_type = self._COND_TYPE_MAP[name]
            # Use a FIXED slot ID that matches the effect type for conditions
            slot = effect_type

            coeff_x = int(props.get('coef_x', props.get('coefficient', 0.0)) * 4096)
            coeff_y = int(props.get('coef_y', props.get('coefficient', 0.0)) * 4096)

            state = self._condition_states.get(name)

            if state is None:
                if slot in self._used_slots:
                    logging.error(f"Slot {slot} for condition effect '{name}' is already in use by another effect!")
                    continue
                self._used_slots.add(slot)

                # header
                self._write_report(bytes(FFBReport_SetEffect(
                    effectBlockIndex=slot,
                    effectType=effect_type,
                    axesEnable=AXIS_ENABLE_X | AXIS_ENABLE_Y)))

                # X axis (parameterBlockOffset 0)
                self._write_report(bytes(FFBReport_SetCondition(
                    effectBlockIndex=slot,
                    parameterBlockOffset=0,
                    positiveCoefficient=coeff_x,
                    negativeCoefficient=coeff_x,
                    positiveSaturation=4096,
                    negativeSaturation=4096,
                    deadBand=0)))

                # Y axis (parameterBlockOffset 1)
                self._write_report(bytes(FFBReport_SetCondition(
                    effectBlockIndex=slot,
                    parameterBlockOffset=1,
                    positiveCoefficient=coeff_y,
                    negativeCoefficient=coeff_y,
                    positiveSaturation=4096,
                    negativeSaturation=4096,
                    deadBand=0)))

                self.start_effect(slot)

                self._condition_states[name] = {
                    'slot': slot,
                    'props': props.copy()
                }
                continue

            # update existing
            slot = state['slot']
            if props != state['props']:
                # Update coefficients if changed
                self._write_report(bytes(FFBReport_SetCondition(
                    effectBlockIndex=slot,
                    parameterBlockOffset=0,
                    positiveCoefficient=coeff_x,
                    negativeCoefficient=coeff_x,
                    positiveSaturation=4096,
                    negativeSaturation=4096,
                    deadBand=0)))

                self._write_report(bytes(FFBReport_SetCondition(
                    effectBlockIndex=slot,
                    parameterBlockOffset=1,
                    positiveCoefficient=coeff_y,
                    negativeCoefficient=coeff_y,
                    positiveSaturation=4096,
                    negativeSaturation=4096,
                    deadBand=0)))

                state['props'] = props.copy()

    def start_effect(self, effect_id):
        # USB PID specification: loopCount=1 means infinite when duration=0. Keeps compatibility with multiple effects.
        op = FFBReport_EffectOperation(effectBlockIndex=effect_id, operation=OP_START, loopCount=1)
        self._write_report(bytes(op))
        
    def stop_effect(self, effect_id):
        op = FFBReport_EffectOperation(effectBlockIndex=effect_id, operation=3) # 3 = OP_STOP
        self._write_report(bytes(op))

    def stop_all_effects(self):
        """Stops all active effects on the joystick."""
        if not self.is_connected:
            return
        
        logging.info("Stopping all joystick effects.")

        # Stop periodic effects
        for name in list(self._periodic_states.keys()):
            state = self._periodic_states.pop(name)
            self.stop_effect(state['slot'])
            self._release_dynamic_slot(state['slot'])

        # Stop condition effects
        for name in list(self._condition_states.keys()):
            state = self._condition_states.pop(name)
            self.stop_effect(state['slot'])
            self._used_slots.discard(state['slot'])
        
        # Stop constant force (slot 2)
        self.stop_effect(2)

    def _write_report(self, data):
        """Wrapper for device.write to handle errors."""
        if not self.is_connected:
            return
        try:
            self.device.write(data)
            time.sleep(0.001)  # Give the device time to process the report
        except (IOError, ValueError) as e:
            logging.error(f"Error writing HID report: {e}")

    def _send_spring_effect(self, axis, props):
        """Constructs and sends a proper FFBReport_SetCondition for a spring."""
        coefficient = int(props.get('coefficient', 0) * 4096)
        offset = int(props.get('cp_offset', 0) * 4096)

        # Create the report structure
        report = FFBReport_SetCondition(
            effectBlockIndex=1,  # Using effect slot 1 for simplicity
            parameterBlockOffset=axis, # 0 for X, 1 for Y
            cpOffset=offset,
            positiveCoefficient=coefficient,
            negativeCoefficient=coefficient,
            positiveSaturation=4096,
            negativeSaturation=4096,
            deadBand=0
        )
        
        try:
            # Convert the ctypes structure to bytes and send it
            self.device.write(bytes(report))
        except (IOError, ValueError) as e:
            logging.error(f"Error sending spring effect: {e}")

    def read_axes(self):
        """
        Reads the current position of the joystick's axes.
        This is now thread-safe and returns the latest value from the reading loop.
        """
        with self.lock:
            return self.axes.copy()

    def close(self):
        """Closes the connection to the joystick."""
        self._quit_event.set()
        if self.is_alive():
            self.join()
        if self.device:
            self.stop_all_effects()
            self.device.close()
        logging.info("Joystick connection closed.")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    joystick = JoystickManager() # Uses default VID/PID

    if joystick.is_connected:
        try:
            print("Joystick connected. Reading axes for 10 seconds...")
            print("Move the joystick to see the values change.")
            for i in range(100):
                axes = joystick.read_axes()
                print(f"Axes: jx={axes.get('jx', 0):.3f}, jy={axes.get('jy', 0):.3f}", end='\r')
                
                joystick.apply_effects({
                    'spring_x': {'coefficient': 0.5, 'cp_offset': 0},
                    'spring_y': {'coefficient': 0.5, 'cp_offset': 0}
                })
                
                time.sleep(0.1)
            print("\nTest complete.")
        except KeyboardInterrupt:
            print("\nExiting.")
        finally:
            joystick.close()
    else:
        print("Could not connect to joystick. Please check connection and ensure it's a VPforce Rhino.")
        # Added a sleep here to allow the background thread to attempt connection
        try:
            time.sleep(11)
            if joystick.is_connected:
                print("Joystick connected after delay.")
            else:
                print("Joystick still not connected.")
        except KeyboardInterrupt:
            pass
        finally:
            joystick.close() 