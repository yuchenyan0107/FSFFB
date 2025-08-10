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
FSFFB Main Application

This is the main entry point for the FSFFB application.
It initializes all the necessary managers and controllers and runs the main loop.
"""

import sys
import logging
import argparse
from queue import Queue, Empty
import time

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread, pyqtSignal

from fsffb.ui.main_window import MainWindow
from fsffb.core.aircraft import get_aircraft_params, save_current_as_preset
from fsffb.telemetry.msfs_manager import MSFSManager
from fsffb.telemetry.xplane_manager import XPlaneManager
from fsffb.hardware.joystick_manager import JoystickManager
from fsffb.core.ffb_calculator import FFBCalculator
from fsffb.hardware.simulator_controller import SimulatorController

class BackendThread(QThread):
    """
    Runs all the backend logic in a separate thread to keep the UI responsive.
    """
    telemetry_updated = pyqtSignal(dict)
    plots_updated = pyqtSignal(dict, dict, dict, dict)
    debug_data_updated = pyqtSignal(dict)
    params_updated = pyqtSignal(dict)  # Signal when parameters are updated

    def __init__(self, simulator_type, params_config):
        super().__init__()
        self.simulator_type = simulator_type
        self.params_config = params_config
        self.telemetry_queue = Queue()
        self.event_queue = Queue()
        self.joystick = None
        self.telemetry_manager = None
        self.ffb_calculator = None
        self.simulator_controller = None
        self._quit = False

    def _telemetry_callback(self, data):
        self.telemetry_queue.put(data)

    def _event_callback(self, event, *args):
        self.event_queue.put((event, args))

    def run(self):
        logging.info(f"Backend thread started for {self.simulator_type.upper()}")

        if self.simulator_type == 'msfs':
            self.telemetry_manager = MSFSManager(self._telemetry_callback, self._event_callback)
        elif self.simulator_type == 'xplane':
            self.telemetry_manager = XPlaneManager(self._telemetry_callback, self._event_callback)
        
        self.joystick = JoystickManager()
        # No longer exit if joystick is not connected initially
            
        self.simulator_controller = SimulatorController(self.telemetry_manager)
        # Initialize the calculator immediately with the default params
        self.ffb_calculator = FFBCalculator(self.params_config)

        self.telemetry_manager.start()

        last_telemetry_time = time.time()
        is_game_paused = False

        while not self._quit:
            # Handle events (simplified for now)
            try:
                event, args = self.event_queue.get_nowait()
                if event == "Quit": self.stop()
            except Empty:
                pass

            # If joystick is not connected, skip telemetry processing
            if not self.joystick.is_connected:
                time.sleep(1) # Wait a bit before checking again
                continue

            # Process telemetry
            try:
                telemetry_data = self.telemetry_queue.get_nowait()
                self.telemetry_updated.emit(telemetry_data)
                last_telemetry_time = time.time()

                if is_game_paused:
                    logging.info("Game resumed, restoring FFB.")
                    is_game_paused = False
                
                joystick_axes = self.joystick.read_axes()
                # Now receives offsets directly from the main processing call
                ffb_effects, sim_axes, virtual_offsets = self.ffb_calculator.process_frame(
                    telemetry_data, joystick_axes
                )
                
                self.joystick.apply_effects(ffb_effects)
                self.simulator_controller.send_axis_data(sim_axes)

                # Emit data for plots using the received offsets
                sim_axes_for_plots = sim_axes if sim_axes is not None else {}
                self.plots_updated.emit(
                    joystick_axes,
                    virtual_offsets,
                    ffb_effects.get('constant_force', {}),
                    sim_axes_for_plots
                )
                
                debug_data = self.ffb_calculator.get_debug_data()
                self.debug_data_updated.emit(debug_data)

            except Empty:
                # Check for game pause state (no telemetry for > 1 second)
                if not is_game_paused and (time.time() - last_telemetry_time > 1.0):
                    logging.info("Game paused, applying idle FFB effects.")
                    is_game_paused = True
                    self.joystick.stop_all_effects()
                    paused_effects = {
                        'spring_x': {'coefficient': 0.3, 'cp_offset': 0},
                        'spring_y': {'coefficient': 0.3, 'cp_offset': 0},
                        'constant_force': {'magnitude': 0, 'direction': 0}
                    }
                    self.joystick.apply_effects(paused_effects)
                
                time.sleep(0.01)
        
        # Shutdown
        if self.telemetry_manager: self.telemetry_manager.quit()
        if self.joystick: self.joystick.close()
        logging.info("Backend thread finished.")

    def update_parameter(self, name, value):
        """Slot to receive parameter changes from the UI."""
        if self.ffb_calculator:
            self.ffb_calculator.update_parameter(name, value)
            # Also update our local params_config
            if name in self.params_config:
                self.params_config[name]['value'] = value
            logging.info(f"Updated parameter '{name}' to {value}")

    def load_preset(self, preset_name):
        """Load a preset and update the FFB calculator."""
        try:
            new_params = get_aircraft_params("default", preset_name)
            
            # Update the FFB calculator with all new parameters
            if self.ffb_calculator:
                for param_name, param_config in new_params.items():
                    self.ffb_calculator.update_parameter(param_name, param_config['value'])
            
            # Update our local params_config
            self.params_config = new_params
            
            # Emit signal to update UI
            self.params_updated.emit(new_params)
            
            logging.info(f"Loaded preset: {preset_name}")
        except Exception as e:
            logging.error(f"Error loading preset {preset_name}: {e}")

    def save_preset(self, preset_name, description):
        """Save current parameters as a preset."""
        try:
            save_current_as_preset(preset_name, self.params_config, description)
            logging.info(f"Saved preset: {preset_name}")
        except Exception as e:
            logging.error(f"Error saving preset {preset_name}: {e}")

    def stop(self):
        self._quit = True

def main():
    parser = argparse.ArgumentParser(description="FSFFB - Force Feedback for Flight Simulators")
    parser.add_argument(
        'simulator',
        nargs='?',
        default='msfs',
        type=str, 
        choices=['msfs', 'xplane'],
        help="The flight simulator you are running (defaults to 'msfs' if not specified)."
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    app = QApplication(sys.argv)
    
    # Get the parameter configuration
    # For now, we use a single default profile. Later, this could load based on aircraft name.
    params_config = get_aircraft_params("default")
    
    # Create and show the main window
    window = MainWindow(params_config)
    
    # Create and start the backend thread
    backend = BackendThread(simulator_type=args.simulator, params_config=params_config)
    
    # Connect signals from backend to slots in UI
    backend.telemetry_updated.connect(window.update_telemetry_display)
    backend.plots_updated.connect(window.update_plots)
    backend.debug_data_updated.connect(window.update_debug_display)
    backend.params_updated.connect(window.update_controls_from_params)
    
    # Connect signals from UI to slots in backend
    window.parameter_changed.connect(backend.update_parameter)
    window.preset_load_requested.connect(backend.load_preset)
    window.preset_save_requested.connect(backend.save_preset)
    
    # Ensure backend stops when the window is closed
    app.aboutToQuit.connect(backend.stop)
    
    backend.start()
    window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main() 