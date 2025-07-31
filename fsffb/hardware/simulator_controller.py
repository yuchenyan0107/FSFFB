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
SimulatorController Module

This module is responsible for sending control inputs (like axis data) back
to the active simulator.
"""

import logging
from fsffb.telemetry.msfs_manager import MSFSManager
from fsffb.telemetry.xplane_manager import XPlaneManager


class SimulatorController:
    """Sends control data to the active simulator."""

    def __init__(self, active_manager):
        """
        Initializes the SimulatorController.

        Args:
            active_manager: An instance of MSFSManager or XPlaneManager.
        """
        self.active_manager = active_manager
        self.is_msfs = isinstance(self.active_manager, MSFSManager)
        self.is_xplane = isinstance(self.active_manager, XPlaneManager)

        if not (self.is_msfs or self.is_xplane):
            raise TypeError("active_manager must be an instance of MSFSManager or XPlaneManager")
            
        logging.info(f"SimulatorController initialized for {'MSFS' if self.is_msfs else 'X-Plane'}")

    def send_axis_data(self, axes):
        """
        Sends joystick axis data to the active simulator.

        Args:
            axes (dict): A dictionary of axis positions from the joystick.
                       If None, no axes will be sent (when send_stick_position is disabled).
        """
        # If axes is None, don't send any data (send_stick_position is disabled)
        if axes is None:
            logging.debug("Stick position sending is disabled - no axes sent to simulator")
            return
            
        if self.is_xplane:
            # X-Plane's plugin expects a dictionary of axes
            self.active_manager.send_axis_data(axes)
        
        elif self.is_msfs:
            # MSFS uses SimConnect events/datums for control
            # This is a simplified example. A real implementation might need
            # to map these generic axes to specific SimConnect L:vars or events.
            if 'jx' in axes:
                # Assuming 'jx' maps to AILERON_SET
                # Note: This is a simplification. Real control might involve
                # setting datums like "L:AILERON_POSITION"
                self.active_manager.send_event("AILERON_SET", int(axes['jx'] * 16383))
            if 'jy' in axes:
                self.active_manager.send_event("ELEVATOR_SET", int(axes['jy'] * 16383))
            #if 'px' in axes:
                 #self.active_manager.send_event("RUDDER_SET", int(axes['px'] * 16383))
        
        logging.debug(f"Sent axes {axes} to {'MSFS' if self.is_msfs else 'X-Plane'}")

    def set_override(self, override_type, enabled):
        """
        Enables or disables control overrides in the simulator.
        This is primarily for X-Plane.

        Args:
            override_type (str): The type of override ('joystick', 'pedals', 'collective').
            enabled (bool): True to enable the override, False to disable.
        """
        if self.is_xplane:
            self.active_manager.set_override(override_type, enabled)
        elif self.is_msfs:
            # MSFS override is handled differently, often by not sending events
            # or by using specific SimVars to disable AI control.
            logging.info("Override command ignored for MSFS in this implementation.")


if __name__ == '__main__':
    import time
    
    # This is a mock setup for demonstration.
    # In a real app, the manager would be running in its own thread.
    class MockManager:
        def send_axis_data(self, axes):
            print(f"MockXPlaneManager: Received axes: {axes}")
        def set_override(self, o, e):
            print(f"MockXPlaneManager: Set override {o} to {e}")

    logging.basicConfig(level=logging.INFO)

    xp_manager = MockManager()
    controller = SimulatorController(xp_manager)

    example_axes = {'jx': 0.75, 'jy': -0.25, 'px': 0.1}
    print("Sending axis data to X-Plane...")
    controller.send_axis_data(example_axes)
    controller.set_override('joystick', True)
    
    # You would need a running instance of MSFSManager or XPlaneManager
    # to test this properly. 