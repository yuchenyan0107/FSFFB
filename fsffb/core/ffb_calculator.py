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
FFBCalculator Module

This module is responsible for calculating force feedback effects based on
telemetry data received from the simulator.
"""

import math
import time
from fsffb.utils import clamp, expocurve, scale, scale_clamp, mix, Vector, Vector2D, LowPassFilter
import numpy as np

# Constants
RAD_TO_DEG = 180 / math.pi
DEG_TO_RAD = math.pi / 180
M_TO_FT = 3.28084
MS_TO_KT = 1.943844
STD_AIR_DENSITY = 1.225  # kg/m^3
VSOUND_ISA = 290.07 # m/s, speed of sound at sea level in ISA condition
P0_ISA = 101325 # Pa, ISA static pressure at sealevel

class FFBCalculator:
    """Calculates FFB effects from telemetry data."""

    def __init__(self, aircraft_params):
        """
        Initializes the FFBCalculator.

        Args:
            aircraft_params (dict): A dictionary of parameters for the
                                    currently loaded aircraft.
        """
        self.params = aircraft_params
        # Store stick force data for potential future use
        self.stick_forces = {
            'pitch': 0.0,
            'roll': 0.0,
            'yaw': 0.0
        }
        self.debug_data = {}
        
        # Time tracking for derivative calculations
        self.last_frame_time = time.time()
        self.previous_values = {}

        # Filters
        self.wind_x_derivative_filter = LowPassFilter(time_constant=0.4)
        self.wind_y_derivative_filter = LowPassFilter(time_constant=1)
        #self.wind_z_derivative_filter = LowPassFilter(time_constant=filter_time_constant)

    def update_parameter(self, name, value):
        """Thread-safe method to update a single parameter."""
        if name in self.params:
            self.params[name]['value'] = value
        else:
            print(f"Warning: Attempted to update non-existent parameter '{name}'")

    def get_stick_forces(self):
        """Returns the current stick force values."""
        return self.stick_forces.copy()

    def get_debug_data(self):
        """Returns collected debug data from the last frame."""
        return self.debug_data.copy()

    def _get_param(self, name, scale=1.0):
        """Helper to get a parameter's value and apply scaling."""
        return self.params[name]['value'] / scale

    def _get_scaled_params(self):
        """Retrieves and scales all parameters from the config dict."""
        p = {}
        for name, config in self.params.items():
            p[name] = config['value']

        # Apply scaling from UI ranges to physics ranges
        p['prop_diameter'] /= 100.0 # in m
        p['aileron_expo'] /= 100.0
        p['elevator_expo'] /= 100.0
        p['max_aileron_coeff'] /= 100.0
        p['max_elevator_coeff'] /= 100.0
        p['g_force_gain'] /= 100.0
        p['elevator_droop_moment'] /= 500.0
        #p['lateral_force_gain'] /= 100.0
        p['stick_shaker_intensity'] /= 100.0
        p['runway_rumble_intensity'] /= 100.0

        # --- Trim Following ---
        p['joystick_trim_follow_gain_physical_y'] /= 100.0
        p['joystick_trim_follow_gain_virtual_y'] /= 100.0
        p['joystick_trim_follow_gain_physical_x'] /= 100.0
        p['joystick_trim_follow_gain_virtual_x'] /= 100.0

        # --- Autopilot Following ---
        p['joystick_ap_follow_gain_physical_y'] /= 100.0
        p['joystick_ap_follow_gain_physical_x'] /= 100.0

        # --- Stick Force Gains ---
        #p['stick_force_pitch_gain'] /= 100.0
        #p['stick_force_roll_gain'] /= 100.0

        p['stall_aoa_ratio'] /= 100.0
        p['wind_gain_x'] /= 100.0
        p['wind_gain_y'] /= 100.0
        p['wind_max_intensity'] /= 100.0

        return p

    def _calculate_time_derivative(self, current_value, variable_name, dt):
        """
        Calculate the time derivative of a variable.
        
        Args:
            current_value: Current value of the variable
            variable_name: Name of the variable for tracking previous values
            dt: Time delta since last frame
            
        Returns:
            float: Time derivative (change per second)
        """
        if dt <= 0:
            return 0.0
            
        if variable_name in self.previous_values:
            previous_value = self.previous_values[variable_name]
            derivative = (current_value - previous_value) / dt
        else:
            derivative = 0.0
            
        # Store current value for next frame
        self.previous_values[variable_name] = current_value
        
        return derivative

    def process_frame(self, telemetry, joystick_axes):
        """
        Calculates all force feedback effects and simulator control inputs.

        Args:
            telemetry (dict): A dictionary of telemetry data from the simulator.
            joystick_axes (dict): Current position of the joystick axes.

        Returns:
            (dict, dict, dict): A tuple containing (ffb_effects, simulator_axes, virtual_offsets)
        """
        if not telemetry:
            self.debug_data = {}
            return {}, {}, {}

        # Calculate time delta for derivative calculations
        current_time = time.time()
        dt = current_time - self.last_frame_time
        self.last_frame_time = current_time

        # Store stick force data from X-Plane telemetry (if available)
        self.stick_forces['pitch'] = telemetry.get('StickForcePitch', 0.0)
        self.stick_forces['roll'] = telemetry.get('StickForceRoll', 0.0)
        self.stick_forces['yaw'] = telemetry.get('StickForceYaw', 0.0)

        # Get all scaled parameters at the beginning of the frame
        p = self._get_scaled_params()

        is_msfs = telemetry.get('src') != 'XPLANE'
        ap_active = (telemetry.get("APMaster", 0) or p['PMDG_AP_On']) if is_msfs else telemetry.get("APServos", 0)

        # 1. Calculate spring center offsets from trim and autopilot
        phys_offsets, virtual_offsets = self._calculate_spring_offsets(telemetry, ap_active, is_msfs, p)

        # 2. Calculate final axis values to send to the simulator
        sim_axes = self._calculate_final_sim_axes(joystick_axes, virtual_offsets, phys_offsets, ap_active)

        # 3. Calculate Aerodynamic Forces (Springs)
        spring_effects, aero_debug_data = self._calculate_aero_spring_forces(telemetry, phys_offsets, p)
        self.debug_data = aero_debug_data

        # 4. Calculate Constant Forces (G-force, droop, wind derivatives)
        constant_effects = self._calculate_constant_forces(telemetry, joystick_axes, p, dt, ap_active)

        # 5. Calculate Vibrations and Other Effects
        vibration_effects = self._calculate_vibration_effects(telemetry, p)
        
        # Combine all effects into a single dictionary
        ffb_effects = {**spring_effects, **constant_effects, **vibration_effects}
        
        return ffb_effects, sim_axes, virtual_offsets

    def _calculate_spring_offsets(self, telem, ap_active, is_msfs, p):
        """Calculates the physical and virtual offsets for the spring center."""
        phys_stick_y_offs = 0
        virtual_stick_y_offs = 0
        phys_stick_x_offs = 0
        virtual_stick_x_offs = 0

        if p['trim_following']:
            # --- Trim Following ---
            elev_trim_pct = telem.get("ElevTrimPct", 0)
            aileron_trim_pct = telem.get("AileronTrimPct", 0)
            
            # Physical offset determines the spring center on the hardware
            phys_y_gain = p['joystick_trim_follow_gain_physical_y']
            phy_x_gain = p['joystick_trim_follow_gain_physical_x']

            phys_stick_y_offs = clamp(elev_trim_pct * phys_y_gain, -1, 1)
            phys_stick_x_offs = clamp(aileron_trim_pct * phy_x_gain, -1, 1)

            # Virtual offset is used to adjust the axis value sent back to the sim
            virtual_y_gain = p['joystick_trim_follow_gain_virtual_y']
            virtual_x_gain = p['joystick_trim_follow_gain_virtual_x']
            virtual_stick_y_offs = -elev_trim_pct * virtual_y_gain
            virtual_stick_x_offs = aileron_trim_pct * virtual_x_gain

        # --- Autopilot Following ---
        if ap_active and self.params['ap_following']['value']:
            if is_msfs:
                if p['ap_trim_only']:
                    phys_stick_y_offs = clamp(elev_trim_pct * phys_y_gain, -1, 1)
                else:
                    elevator_pos = telem.get("ElevDeflPct", 0)
                    ap_y_gain_phys = p['joystick_ap_follow_gain_physical_y']
                    phys_stick_y_offs = clamp(elevator_pos * ap_y_gain_phys, -1, 1)

                aileron_pos = (telem.get("AileronDeflPctLR", 0)[0]+telem.get("AileronDeflPctLR", 0)[1])/2
                ap_x_gain_phys = p['joystick_ap_follow_gain_physical_x']
                phys_stick_x_offs = clamp(aileron_pos * ap_x_gain_phys, -1, 1)

                virtual_stick_y_offs = 0
                virtual_stick_x_offs = 0

            else: # X-Plane
                elevator_pos = telem.get("APPitchServo", 0)
                phys_stick_y_offs = clamp(elevator_pos, -1, 1)

                virtual_stick_y_offs = 0
                virtual_stick_x_offs = 0

        phys_offsets = {'x': phys_stick_x_offs, 'y': phys_stick_y_offs}
        virtual_offsets = {'x': virtual_stick_x_offs, 'y': virtual_stick_y_offs}
        
        return phys_offsets, virtual_offsets

    def _calculate_final_sim_axes(self, joystick_axes, virtual_offsets, phys_offsets, ap_active):
        """Calculates the final axis values to send to the simulator."""
        # Check if stick position should be sent to the game
        send_stick_position = self.params.get('send_stick_position', {}).get('value', True)
        
        if not send_stick_position:
            return None  # Don't send stick position to the game
        
        phys_x = joystick_axes.get('jx', 0)
        phys_y = -joystick_axes.get('jy', 0)

        deflection_x = abs(phys_offsets['x'] - joystick_axes.get('jx', 0))
        deflection_y = abs(phys_offsets['y'] - joystick_axes.get('jy', 0))
        
        if ap_active and (deflection_x < 0.3) and (deflection_y < 0.3):
            sim_x = 0
            sim_y = 0
        else:
            sim_x = -(phys_x - virtual_offsets['x'])
            sim_y = phys_y - virtual_offsets['y']
        
        return {'jx': sim_x, 'jy': sim_y, 'px': joystick_axes.get('px', 0)}

    def _calculate_aero_spring_forces(self, telem, phys_offsets, p):
        """Calculates the main aerodynamic spring forces on the control surfaces."""
        
        # --- 1. Get Core Variables ---
        ias = telem.get('IAS', 0)
        dyn_pressure = telem.get('DynPressure', 0)
        air_density = telem.get('AirDensity', STD_AIR_DENSITY)
        
        # --- 2. Calculate Prop Wash ---
        if p['prop_diameter'] > 0:
            prop_thrust = max(telem.get('PropThrust', [0])) if isinstance(telem.get('PropThrust'), list) else telem.get('PropThrust', 0)
            prop_thrust *= 4.4482216152605
            prop_diameter = p['prop_diameter']
            prop_air_vel = math.sqrt(2 * max(0, prop_thrust) / (air_density * (math.pi * (prop_diameter / 2)**2)) + ias**2)-ias

            mixing_factor = np.exp(-abs(telem.get('AoA', 0)-3) / 8.6) * np.exp(-(telem.get('SideSlip', 0) / 10)**2)
            elev_dyn_pressure = dyn_pressure+(0.5 * air_density * prop_air_vel**2)*mixing_factor
        else:
            prop_air_vel = 0
            elev_dyn_pressure = dyn_pressure

        aileron_dyn_pressure = dyn_pressure
        
        # --- 3. Vne Scaling ---
        # Normalize forces based on never-exceed speed to keep them in a reasonable range.
        if telem.get('src') == 'XPLANE':
            vne = telem.get('Vne', 250 * MS_TO_KT)
        else: # MSFS
            vc, _, _ = telem.get("DesignSpeed", (150 * MS_TO_KT, 0, 0))
            Tvne = vc * 1.4
            qv = (0.5 * STD_AIR_DENSITY * (Tvne ** 2))
            kmNs = ((( qv / P0_ISA) + 1) ** (2/7))
            vne = VSOUND_ISA * math.sqrt(5 * ( kmNs - 1))
            
        vne_override = p['vne_override']
        if vne_override > 0:
            vne = vne_override / MS_TO_KT
            
        Qvne = 0.5 * STD_AIR_DENSITY * vne**2
        Q_gain = 1 / (Qvne) if Qvne > 0 else 0
        
        # --- 4. Calculate Final Coefficients ---
        base_aileron_coeff = aileron_dyn_pressure * Q_gain
        base_elevator_coeff = elev_dyn_pressure * Q_gain
        
        aileron_coeff = expocurve(base_aileron_coeff, p['aileron_expo'])
        elevator_coeff = expocurve(base_elevator_coeff, p['elevator_expo'])

        # Clamp to max values
        max_aileron_coeff = p['max_aileron_coeff'] # Scale from 0-100 slider
        max_elevator_coeff = p['max_elevator_coeff']
        final_aileron_coeff = scale_clamp(aileron_coeff, (0, 1), (0, max_aileron_coeff))
        final_elevator_coeff = scale_clamp(elevator_coeff, (0, 1), (0, max_elevator_coeff))

        # --- 5. Calculate Stall Effects ---

        stall_aoa = telem.get('StallAoA', 0) * p['stall_aoa_ratio']
        aoa = telem.get('AoA', 0)

        if (aoa > stall_aoa) & (not telem.get('SimOnGround', False)):
            final_aileron_coeff *= np.exp(-(aoa-stall_aoa)/5)

            elev_coef_tem = np.copy(final_elevator_coeff)
            final_elevator_coeff *= 2 - np.exp((aoa-stall_aoa)/6)
            final_aileron_coeff = clamp(final_aileron_coeff, 0, 1)
            final_elevator_coeff = clamp(final_elevator_coeff, elev_coef_tem*0.2, 1)

            damper_aileron = (aoa - stall_aoa)/10
        else:
            damper_aileron = 0
        

        spring_effects = {
            'spring_x': {
                'coefficient': final_aileron_coeff,
                'cp_offset': phys_offsets['x'] 
            },
            'spring_y': {
                'coefficient': final_elevator_coeff,
                'cp_offset': phys_offsets['y']
            }
        }

        debug_data = {
            'spring_coeff_x': final_aileron_coeff,
            'spring_coeff_y': final_elevator_coeff,
            'elev_dyn_pressure': elev_dyn_pressure,
            'aileron_dyn_pressure': aileron_dyn_pressure,
            'mixing_factor': mixing_factor,
            'prop air vel': prop_air_vel,
            'damper_aileron': damper_aileron
        }
        
        return spring_effects, debug_data

    def _calculate_constant_forces(self, telem, joystick_axes, p, dt, ap_active):
        """Calculates constant forces like G-force, control surface droop, and wind derivatives."""
        
        accel_body = telem.get('AccBody', (0, 0, 0)) # Y-component for Gs
        g_force = telem.get('G', 1.0)
        dyn_pressure = telem.get('DynPressure', 0)
        
        g_force_gain = p['g_force_gain'] # Scale from 0-100 slider
        #g_term = g_force_gain * (accel_body[1] + 0) #* abs(joystick_axes.get('jy', 0))
        g_term = g_force_gain * (g_force-1)

        elevator_droop_moment = p['elevator_droop_moment']
        elevator_droop_term = elevator_droop_moment * g_force / (1 + dyn_pressure)
        
        # Calculate time derivative of WindX
        wind_x = telem.get('WindX', 0.0) # East/West
        wind_x_derivative = self._calculate_time_derivative(wind_x, 'WindX', dt)

        wind_z = telem.get('WindZ', 0.0) # North/South
        wind_z_derivative = self._calculate_time_derivative(wind_z, 'WindZ', dt)

        wind_y = telem.get('WindY', 0.0) # vertical 
        wind_y_derivative = self._calculate_time_derivative(wind_y, 'WindY', dt)

        angle = telem.get('Heading', 0) * RAD_TO_DEG

        #wind_on_aircraft_x = wind_x * math.cos(angle * DEG_TO_RAD) - wind_z * math.sin(angle * DEG_TO_RAD)
        #wind_on_aircraft_z = wind_z * math.cos(angle * DEG_TO_RAD) + wind_x * math.sin(angle * DEG_TO_RAD)

        wind_on_aircraft_x_derivative = wind_x_derivative * math.cos(angle * DEG_TO_RAD) - wind_z_derivative * math.sin(angle * DEG_TO_RAD)
        wind_on_aircraft_z_derivative = wind_z_derivative * math.cos(angle * DEG_TO_RAD) + wind_x_derivative * math.sin(angle * DEG_TO_RAD)
        
        # Filter the derivatives
        filtered_wind_x_derivative = self.wind_x_derivative_filter.process(wind_on_aircraft_x_derivative, dt)
        filtered_wind_y_derivative = self.wind_y_derivative_filter.process(wind_y_derivative, dt)

        wind_derivative_x_term = filtered_wind_x_derivative * p['wind_gain_x']
        wind_derivative_y_term = filtered_wind_y_derivative * p['wind_gain_y']

        wind_derivative_x_term = clamp(wind_derivative_x_term, -p['wind_max_intensity'], p['wind_max_intensity'])
        wind_derivative_y_term = clamp(wind_derivative_y_term, -p['wind_max_intensity'], p['wind_max_intensity'])

        stick_force_pitch = 0
        stick_force_roll = 0
        '''
        # --- Stick Force Integration (X-Plane specific) ---
        if telem.get('src') == 'XPLANE':
            stick_force_pitch = telem.get('StickForcePitch', 0.0) * p['stick_force_pitch_gain']
            stick_force_roll = -telem.get('StickForceRoll', 0.0) * p['stick_force_roll_gain']
        '''
        # --- Combine and normalize forces ---
        pitch_force = clamp(-elevator_droop_term - g_term + stick_force_pitch - wind_derivative_y_term, -1.0, 1.0)
        roll_force = clamp( + stick_force_roll - wind_derivative_x_term, -1.0, 1.0)
        
        force_vec = Vector2D(roll_force, pitch_force)
            
        magnitude, direction = force_vec.to_polar()

        if ap_active:
            magnitude = 0

        # Store debug information
        self.debug_data.update({
            'wind_y': wind_y,
            'wind_y_derivative_filtered': filtered_wind_y_derivative,
            'ap_active': ap_active,
        })
 
        return {
            'constant_force': {
                'magnitude': magnitude,
                'direction': direction * RAD_TO_DEG
            }
        }

    def _calculate_vibration_effects(self, telem, p):
        """Calculates vibration effects like stall, runway rumble, etc."""
        effects = {}

        # aileron stall
        aoa = telem.get('AoA', 0)
        stall_aoa = telem.get('StallAoA', 0) * p['stall_aoa_ratio']
        if (aoa > stall_aoa) & (not telem.get('SimOnGround', False)):
            shaker_intensity = (1 - abs(aoa-(stall_aoa*1.2))/(stall_aoa*0.3)) * p['stick_shaker_intensity']
            effects['stick_shaker_1'] = {
                'type': 'periodic',
                'waveform': 'sine',
                'frequency': 13,
                'magnitude': shaker_intensity,
                'direction': 0
            }

            damper_aileron = expocurve((aoa-stall_aoa)/6, 0.4)*0.5
        else:
            damper_aileron = 0

        # elevator stall
        if (aoa > stall_aoa) & (not telem.get('SimOnGround', False)):
            shaker_intensity = (1 - abs(aoa-(stall_aoa*1.2))/(stall_aoa*0.3)) * p['stick_shaker_intensity']
            effects['stick_shaker_2'] = {
                'type': 'periodic',
                'waveform': 'sine',
                'frequency': 18,
                'magnitude': shaker_intensity,
                'direction': 90
            }
            
        if telem.get('SimOnGround', False):
            speed_kts = telem.get('GroundSpeed', 0) * MS_TO_KT
            if speed_kts > 5:
                rumble_intensity = p['runway_rumble_intensity']
                intensity = scale_clamp(speed_kts, (5, 80), (0.1, rumble_intensity))
                frequency = scale_clamp(speed_kts, (5, 80), (15, 60))
                effects['runway_rumble_1'] = {
                    'type': 'periodic', 
                    'waveform': 'sine', 
                    'frequency': frequency,
                    'magnitude': intensity, 
                    'direction': 90
                }
        
        if telem.get('SimOnGround', False):
            speed_kts = telem.get('GroundSpeed', 0) * MS_TO_KT
            if speed_kts > 20:
                rumble_intensity = p['runway_rumble_intensity']
                intensity = scale_clamp(speed_kts, (5, 80), (0.1, rumble_intensity))
                frequency = scale_clamp(speed_kts, (5, 80), (15, 60))
                effects['runway_rumble_2'] = {
                    'type': 'periodic', 
                    'waveform': 'sine', 
                    'frequency': frequency,
                    'magnitude': intensity, 
                    'direction': 180
                }

        if p['test1']:
            effects['test1'] = {
                'type': 'periodic',
                'waveform': 'sine',
                'frequency': 15,
                'magnitude': 0.4,
                'direction': 0
            }
        if p['test2']:
            effects['test2'] = {
                'type': 'periodic',
                'waveform': 'sine',
                'frequency': 10,
                'magnitude': 0.7,
                'direction': 90
            }


        # --- Damper, Inertia, Friction ---

        damper_aileron += p['damper_coef'] / 100.0
        damper_aileron = clamp(damper_aileron, 0, 0.8)

        effects['damper'] = {'coef_x': damper_aileron, 'coef_y': p['damper_coef'] / 100.0}
        effects['inertia'] = {'coef_x': 0, 'coef_y': 0}
        effects['friction'] = {'coef_x': 0, 'coef_y': 0}

        return effects 