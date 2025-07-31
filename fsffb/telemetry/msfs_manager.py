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
MSFSManager Module

This module provides a SimConnect interface for Microsoft Flight Simulator (MSFS) telemetry.
It manages communication with MSFS via SimConnect to retrieve aircraft telemetry data.
"""

from SimConnect import *
from ctypes import byref, cast, sizeof
import time
import threading
import logging
import os


surface_types = {
    0: "Concrete", 1: "Grass", 2: "Water", 3: "Grass_bumpy", 4: "Asphalt",
    5: "Short_grass", 6: "Long_grass", 7: "Hard_turf", 8: "Snow", 9: "Ice",
    10: "Urban", 11: "Forest", 12: "Dirt", 13: "Coral", 14: "Gravel",
    15: "Oil_treated", 16: "Steel_mats", 17: "Bituminus", 18: "Brick",
    19: "Macadam", 20: "Planks", 21: "Sand", 22: "Shale", 23: "Tarmac",
    24: "Wright flyer track",
}

class SimVar:
    """Represents a single simulation variable from MSFS."""
    def __init__(self, name, var, sc_unit, unit=None, datatype=DATATYPE_FLOAT64, scale=None, mutator=None):
        self.name = name
        self.var = var
        self.scale = scale
        self.mutator = mutator
        self.sc_unit = sc_unit
        self.unit = unit
        self.datatype = datatype
        self.parent = None
        self.index = None
        if self.sc_unit.lower() in ["bool", "enum"]:
            self.datatype = DATATYPE_INT32

    def _calculate(self, input):
        if self.mutator:
            input = self.mutator(input)
        if self.scale:
            input = input * self.scale
        return input

    def __repr__(self):
        return f"SimVar({self.name} '{self.var}')"

    @property
    def c_type(self):
        types = {
            DATATYPE_FLOAT64: c_double, DATATYPE_FLOAT32: c_float,
            DATATYPE_INT32: c_long, DATATYPE_STRING32: c_char * 32,
            DATATYPE_STRING128: c_char * 128
        }
        return types.get(self.datatype, c_double)

class SimVarArray:
    """Represents an array of related simulation variables from MSFS."""
    def __init__(self, name, var, unit, type=DATATYPE_FLOAT64, scale=None, min=0, max=1, keywords=None):
        self.name = name
        self.var = var
        self.unit = unit
        self.type = type
        self.scale = scale
        self.vars = []
        self.values = []
        self.min = min
        self.max = max
        self.keywords = keywords
        if keywords:
            for i, key in enumerate(keywords):
                simvar_name = var.replace("<>", key)
                v = SimVar(name, simvar_name, unit, None, type, scale)
                v.index = i
                v.parent = self
                self.vars.append(v)
                self.values.append(0)
        else:
            for i in range(min, max + 1):
                v = SimVar(name, f"{var}:{i}", unit, None, type, scale)
                v.index = i - min  # Adjust index to be 0-based for the values array
                v.parent = self
                self.vars.append(v)
                self.values.append(0)

    def clone(self):
        return SimVarArray(
            self.name, self.var, self.unit, type=self.type, scale=self.scale,
            min=self.min, max=self.max, keywords=self.keywords
        )

EV_PAUSED = 65499
EV_STARTED = 65498
EV_STOPPED = 65497
EV_SIMSTATE = 65496

class MSFSManager(threading.Thread):
    """Manages SimConnect communication with Microsoft Flight Simulator."""
    def __init__(self, telemetry_callback, event_callback):
        threading.Thread.__init__(self, daemon=True)
        self.telemetry_callback = telemetry_callback
        self.event_callback = event_callback
        self.sc = None
        self._quit = False
        self.initial_subscribe_done = False
        self._sim_paused = False
        self._sim_started = 0
        self._sim_state = 0
        self._stop_state = 0
        self._events_to_send = []
        self._simdatums_to_send = []
        self.subscribed_vars = []
        self.temp_sim_vars = []
        self.temp_sv_array_element = []
        self.resubscribe = False
        self.current_simvars = []
        self.current_var_tracker = []
        self.new_var_tracker = []
        self.req_id = os.getpid()
        self.def_id = os.getpid()
        self.sv_dict = {}
        self.connected_version = None
        self.sim_vars = self._get_default_simvars()

    def _get_default_simvars(self):
        """Returns a list of default SimVar and SimVarArray objects."""
        return [
            SimVar("T", "ABSOLUTE TIME", "Seconds"),
            SimVar("N", "TITLE", "", datatype=DATATYPE_STRING128),

            SimVar("G", "G FORCE", "Number"),
            SimVarArray("VelRotBody", "ROTATION VELOCITY BODY <>", "degrees per second", keywords=("X", "Y", "Z")),
            SimVarArray("AccBody", "ACCELERATION BODY <>", "feet per second squared", scale=0.031081, keywords=("X", "Y", "Z")),
            SimVar("AoA", "INCIDENCE ALPHA", "degrees"),
            SimVar("SideSlip", "INCIDENCE BETA", "degrees"),

            SimVar("Pitch", "PLANE PITCH DEGREES", "degrees"),
            SimVar("Roll", "PLANE BANK DEGREES", "degrees"),
            SimVar("Heading", "PLANE HEADING DEGREES TRUE", "degrees"),
            
            SimVar("TAS", "AIRSPEED TRUE", "meter/second"),
            SimVar("IAS", "AIRSPEED INDICATED", "meter/second"),
            SimVar("AirDensity", "AMBIENT DENSITY", "kilograms per cubic meter"),
            SimVar("DynPressure", "DYNAMIC PRESSURE", "pascal"),
            
            SimVar("StallAoA", "STALL ALPHA", "degrees"),
            
            SimVar("ElevDefl", "ELEVATOR DEFLECTION", "degrees"),
            SimVar("ElevDeflPct", "ELEVATOR DEFLECTION PCT", "Percent Over 100"),
            SimVar("AileronDefl", "AILERON AVERAGE DEFLECTION", "degrees"),
            SimVarArray("AileronDeflPctLR", "AILERON <> DEFLECTION PCT", keywords=("LEFT", "RIGHT"), unit="Percent Over 100"),
            SimVar("RudderDefl", "RUDDER DEFLECTION", "degrees"),
            SimVar("RudderDeflPct", "RUDDER DEFLECTION PCT", "Percent Over 100"),

            SimVar("ElevTrim", "ELEVATOR TRIM POSITION", "degrees"),
            SimVar("ElevTrimPct", "ELEVATOR TRIM PCT", "Percent Over 100"),
            SimVar("ElevTrimDnLmt", "ELEVATOR TRIM DOWN LIMIT", "degrees"),
            SimVar("ElevTrimUpLmt", "ELEVATOR TRIM UP LIMIT", "degrees"),
            SimVar("ElevTrimNeutral", "ELEVATOR TRIM NEUTRAL", "degrees"),

            SimVar("AileronTrim", "AILERON TRIM", "degrees"),
            SimVar("AileronTrimPct", "AILERON TRIM PCT", "Percent Over 100"),
            
            SimVar('CameraState', "CAMERA STATE", "Enum"),
            SimVar("GroundSpeed", "GROUND VELOCITY", "meter/second"),
            SimVar("SimOnGround", "SIM ON GROUND", "Bool"),
            SimVar("Parked", "PLANE IN PARKING STATE", "Bool"),
            SimVar("Slew", "IS SLEW ACTIVE", "Bool"),
            SimVar("SurfaceType", "SURFACE TYPE", "Enum", mutator=lambda x: surface_types.get(x, "unknown")),
            SimVar("EngineType", "ENGINE TYPE", "Enum"),
            SimVar("NumEngines", "NUMBER OF ENGINES", "Number", datatype=DATATYPE_INT32),
            SimVarArray("WeightOnWheels", "CONTACT POINT COMPRESSION", "Number", min=0, max=2),

            SimVar("APMaster", "AUTOPILOT MASTER", "Bool"),
            SimVarArray("PropThrust", "PROP THRUST", "pounds", min=0, max=3),
            SimVar("SideSlip", "INCIDENCE BETA", "degrees"),

            SimVar("WindX", "AMBIENT WIND X", "meter/second"),
            SimVar("WindY", "AMBIENT WIND Y", "meter/second"),
            SimVar("WindZ", "AMBIENT WIND Z", "meter/second"),

            SimVar("WindDirection", "AMBIENT WIND DIRECTION", "degrees"),
            SimVar("WindVelocity", "AMBIENT WIND VELOCITY", "meter/second"),
            SimVar("Heading", "PLANE HEADING DEGREES TRUE", "radians"),

        ]

    def add_simvar(self, name, var, sc_unit, **kwargs):
        """Queue a simvar to be added or overridden."""
        if ":" in name:
            sv = SimVar(name.split(":")[0], var, sc_unit, **kwargs)
            sv.index = int(name.split(":")[1])
            self.temp_sv_array_element.append(sv)
        else:
            self.temp_sim_vars.append(SimVar(name, var, sc_unit, **kwargs))

    def substitute_simvars(self):
        """Build the final list of simulation variables to subscribe to."""
        master_list = list(self.sim_vars)
        override_list = list(self.temp_sim_vars)

        master_dict = {sv.name: sv for sv in master_list}
        override_dict = {sv.name: sv for sv in override_list}

        for sv_array_override in self.temp_sv_array_element:
            sv_array = master_dict.get(sv_array_override.name)
            if sv_array and sv_array_override.name not in override_dict:
                override_dict[sv_array_override.name] = sv_array.clone()

        for sv in self.temp_sv_array_element:
            sv_array = override_dict.get(sv.name)
            if sv_array and 0 <= int(sv.index) < len(sv_array.vars):
                sv_array.vars[int(sv.index)] = sv
                sv.parent = sv_array

        master_dict.update(override_dict)
        self.temp_sim_vars.clear()
        self.temp_sv_array_element.clear()

        final_list = list(master_dict.values())
        self.new_var_tracker = [sv.var for sv in final_list if isinstance(sv, SimVar)]
        for sva in [sv for sv in final_list if isinstance(sv, SimVarArray)]:
            self.new_var_tracker.extend([v.var for v in sva.vars])

        self.sv_dict = {sv.name: sv.var for sv in final_list if isinstance(sv, SimVar)}
        for sva in [sv for sv in final_list if isinstance(sv, SimVarArray)]:
             for v in sva.vars:
                self.sv_dict[f"{sva.name}:{v.index}"] = v.var

        return final_list

    def _subscribe(self):
        """Subscribe to simulation variables with SimConnect."""
        sim_vars = self.substitute_simvars()

        if self.current_var_tracker == self.new_var_tracker:
            return

        logging.info("Simvar list has changed, creating new SC subscription")
        if self.initial_subscribe_done:
            self.sc.ClearDataDefinition(self.def_id)
            self.def_id += 1
        self.initial_subscribe_done = True

        self.subscribed_vars.clear()
        self.current_var_tracker.clear()

        i = 0
        for sv in sim_vars:
            if isinstance(sv, SimVarArray):
                for v in sv.vars:
                    self.sc.AddToDataDefinition(self.def_id, v.var, v.sc_unit, v.datatype, 0, i)
                    self.subscribed_vars.append(v)
                    i += 1
            else:
                self.sc.AddToDataDefinition(self.def_id, sv.var, sv.sc_unit, sv.datatype, 0, i)
                self.subscribed_vars.append(sv)
                i += 1
        self.current_var_tracker = self.new_var_tracker

        self.sc.RequestDataOnSimObject(
            self.req_id, self.def_id, OBJECT_ID_USER,
            PERIOD_SIM_FRAME, DATA_REQUEST_FLAG_TAGGED, 0, 1, 0
        )

    def request_resubscribe(self):
        """Request a resubscription on the next telemetry read cycle."""
        self.resubscribe = True

    def set_simdatum(self, simvar, value, units=None):
        """Queue a simulation datum to be sent to MSFS."""
        self._simdatums_to_send.append((simvar, value, units))

    def send_event(self, event, data: int = 0):
        """Queue an event to be sent to MSFS."""
        if event == "DO_NOT_SEND":
            return
        self._events_to_send.append((event, data))

    def _tx_simdatums(self):
        """Transmit all queued simulation datums to MSFS."""
        while self._simdatums_to_send:
            simvar, value, units = self._simdatums_to_send.pop(0)
            try:
                self.sc.set_simdatum(simvar, value, units=units)
            except Exception as e:
                logging.error(f"Error sending {simvar} value {value} to MSFS: {e}")

    def _tx_events(self):
        """Transmit all queued events to MSFS."""
        while self._events_to_send:
            event, data = self._events_to_send.pop(0)
            if event.startswith('L:'):
                self.set_simdatum(event, data, units="number")
            else:
                try:
                    self.sc.send_event(event, data)
                except Exception as e:
                    logging.error(f"Error setting event:{event} value:{data} to MSFS: {e}")

    def _read_telem(self):
        """Main telemetry reading loop."""
        pRecv = RECV_P()
        nSize = DWORD()

        while not self._quit:
            self._tx_events()
            self._tx_simdatums()

            try:
                self.sc.GetNextDispatch(byref(pRecv), byref(nSize))
            except OSError:
                time.sleep(0.001)
                continue

            if self.resubscribe:
                self._subscribe()
                self.resubscribe = False
                continue

            recv = ReceiverInstance.cast_recv(pRecv)
            if isinstance(recv, RECV_EXCEPTION):
                logging.error(f"SimConnect exception {recv.dwException}, sendID {recv.dwSendID}, index {recv.dwIndex}")
            elif isinstance(recv, RECV_QUIT):
                logging.info("Quit received")
                self.event_callback("Quit")
                break
            elif isinstance(recv, RECV_OPEN):
                msfs_vers = recv.szApplicationName.decode('utf-8')
                if msfs_vers == 'SunRise':
                    self.connected_version = "MSFS2024"
                elif msfs_vers == "KittyHawk":
                    self.connected_version = "MSFS2020"
                else:
                    self.connected_version = msfs_vers
                self.event_callback("Open")
            elif isinstance(recv, RECV_EVENT):
                self._handle_event(recv)
            elif isinstance(recv, RECV_SIMOBJECT_DATA):
                self._handle_simobject_data(recv)
            else:
                logging.warning(f"Received unknown simconnect message: {recv}")

    def _handle_event(self, recv):
        """Handle system events from SimConnect."""
        event_map = {
            EV_PAUSED: ("Paused", "dwData"),
            EV_STARTED: ("SimStart", None),
            EV_STOPPED: ("SimStop", None),
            EV_SIMSTATE: ("SimState", "dwData")
        }
        event_name, data_attr = event_map.get(recv.uEventID, (None, None))

        if event_name:
            logging.debug(f"EVENT {event_name.upper()}, EVENT: {recv.uEventID}, DATA: {getattr(recv, data_attr) if data_attr else 'N/A'}")
            if recv.uEventID == EV_PAUSED: self._sim_paused = recv.dwData
            if recv.uEventID == EV_STARTED: self._sim_started = 1
            if recv.uEventID == EV_STOPPED: self._sim_started = 0
            if recv.uEventID == EV_SIMSTATE: self._sim_state = recv.dwData

            data = getattr(recv, data_attr) if data_attr else None
            self.event_callback(event_name, data)

    def _handle_simobject_data(self, recv):
        """Handle telemetry data packets from SimConnect."""
        if recv.dwRequestID != self.req_id or recv.dwDefineID != self.def_id:
            return

        data = {"SimPaused": self._sim_paused}
        offset = RECV_SIMOBJECT_DATA.dwData.offset
        for _ in range(recv.dwDefineCount):
            try:
                idx = cast(byref(recv, offset), POINTER(DWORD))[0]
                offset += sizeof(DWORD)
                var: SimVar = self.subscribed_vars[idx]
                c_type = var.c_type
                if var.datatype == DATATYPE_STRING128:
                    val = str(cast(byref(recv, offset), POINTER(c_type))[0].value, "utf-8")
                else:
                    val = cast(byref(recv, offset), POINTER(c_type))[0]
                offset += sizeof(c_type)
                val = var._calculate(val)

                if var.parent:
                    var.parent.values[var.index] = val
                    data[var.parent.name] = var.parent.values
                else:
                    data[var.name] = val
            except (IndexError, AttributeError) as e:
                logging.error(f"Error parsing SimConnect data: {e}")
                continue

        in_menus = data.get('CameraState', 0) not in (2, 3, 4, 5)
        is_stopped = self._sim_paused or data.get("Parked", 0) or data.get("Slew", 0) or in_menus

        if is_stopped:
            data["STOP"] = 1
            if not self._stop_state:
                self.event_callback("STOP")
                self.telemetry_callback(data)
                self._stop_state = True
        else:
            self._stop_state = False
            self.telemetry_callback(data)

    def quit(self):
        """Request the manager thread to quit."""
        self._quit = True

    def run(self):
        """Main thread execution method."""
        while not self._quit:
            try:
                logging.info("Trying to connect to SimConnect...")
                with SimConnect("FSFFB") as self.sc:
                    logging.info("SimConnect connection established.")
                    self.sc.SubscribeToSystemEvent(EV_PAUSED, "Pause")
                    self.sc.SubscribeToSystemEvent(EV_STARTED, "SimStart")
                    self.sc.SubscribeToSystemEvent(EV_STOPPED, "SimStop")
                    self.sc.SubscribeToSystemEvent(EV_SIMSTATE, "Sim")
                    self._subscribe()
                    self._read_telem()
            except OSError:
                logging.warning("SimConnect connection failed, retrying in 10 seconds.")
                time.sleep(10)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    def on_telemetry(data):
        print(f"Received telemetry: {data}")

    def on_event(event, *args):
        print(f"Received event: {event}, args: {args}")

    s = MSFSManager(on_telemetry, on_event)
    s.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        s.quit()
        s.join()
        print("Exiting.") 