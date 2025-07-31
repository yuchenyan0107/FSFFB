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
XPlaneManager Module

This module provides an interface for X-Plane telemetry and control.
It communicates with the FSFFB-XPP plugin via UDP to receive telemetry data
and send control inputs.
"""

import socket
import threading
import logging
from collections import deque

class XPlaneManager(threading.Thread):
    """Manages communication with the X-Plane plugin."""

    def __init__(self, telemetry_callback, event_callback):
        """
        Initializes the XPlaneManager.

        Args:
            telemetry_callback (callable): Function to call with new telemetry data.
            event_callback (callable): Function to call with system events.
        """
        threading.Thread.__init__(self, daemon=True)
        self.telemetry_callback = telemetry_callback
        self.event_callback = event_callback
        self._quit = False
        self.rx_socket = None
        self.tx_socket = None
        self.command_queue = deque()

        self._setup_sockets()

    def _setup_sockets(self):
        """Initializes the UDP sockets for receiving and sending data."""
        try:
            # RX Socket (Telemetry from X-Plane)
            self.rx_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.rx_socket.bind(('127.0.0.1', 34390))
            self.rx_socket.settimeout(1.0)
            logging.info("X-Plane telemetry socket listening on port 34390.")

            # TX Socket (Commands to X-Plane)
            self.tx_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            logging.info("X-Plane command socket ready to send on port 34391.")

        except OSError as e:
            logging.error(f"Error setting up X-Plane sockets: {e}")
            self.rx_socket = None
            self.tx_socket = None

    def run(self):
        """Main loop for the manager thread."""
        
        while not self._quit:
            if not self.rx_socket:
                # Sockets failed to initialize, so we can't do anything.
                time.sleep(1)
                continue

            # Process outgoing commands
            while self.command_queue:
                command = self.command_queue.popleft()
                self._send_command(command)

            # Receive incoming telemetry
            try:
                data, _ = self.rx_socket.recvfrom(4096)
                telemetry = self._parse_telemetry(data.decode('utf-8'))
                if telemetry:
                    self.telemetry_callback(telemetry)
            except socket.timeout:
                continue
            except Exception as e:
                logging.error(f"Error receiving or parsing X-Plane telemetry: {e}")

        self._cleanup()

    def _parse_telemetry(self, data_string):
        """Parses the key-value telemetry string from X-Plane."""
        telemetry = {}
        try:
            pairs = data_string.strip(';').split(';')
            for pair in pairs:
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    telemetry[key] = self._convert_value(value)
            return telemetry
        except Exception as e:
            logging.warning(f"Could not parse telemetry string: '{data_string}'. Error: {e}")
            return None

    def _convert_value(self, value_str):
        """Tries to convert a string value to a more appropriate type."""
        if '~' in value_str:
            return [self._convert_value(v) for v in value_str.split('~')]
        try:
            if '.' in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            return value_str

    def _send_command(self, command_str):
        """Sends a command string to the X-Plane plugin."""
        if self.tx_socket:
            try:
                self.tx_socket.sendto(command_str.encode('utf-8'), ('127.0.0.1', 34391))
            except Exception as e:
                logging.error(f"Error sending command to X-Plane: {e}")

    def send_axis_data(self, axes):
        """
        Sends axis data to X-Plane.

        Args:
            axes (dict): A dictionary of axis values (e.g., {'jx': 0.5, 'jy': -0.2}).
        """
        payload = ",".join([f"{key}={value}" for key, value in axes.items()])
        self.command_queue.append(f"AXIS:{payload}")

    def set_override(self, override_type, enabled):
        """
        Enables or disables control overrides in X-Plane.

        Args:
            override_type (str): The type of override ('joystick', 'pedals', 'collective').
            enabled (bool): True to enable the override, False to disable.
        """
        self.command_queue.append(f"OVERRIDE:{override_type}={str(enabled).lower()}")
        
    def subscribe_dataref(self, dataref, type, tag, precision=3, conversion=1.0):
        """
        Requests the plugin to subscribe to an additional DataRef.
        
        Args:
            dataref (str): The X-Plane DataRef path (e.g., "sim/flightmodel/position/latitude").
            type (str): The data type ('float', 'int', 'double').
            tag (str): The key to use for this value in the telemetry data.
            precision (int): The floating point precision.
            conversion (float): A factor to multiply the value by.
        """
        payload = f"dataref={dataref},type={type},tag={tag},precision={precision},conversion={conversion}"
        self.command_queue.append(f"SUBSCRIBE:{payload}")

    def quit(self):
        """Signals the manager to shut down."""
        self._quit = True

    def _cleanup(self):
        """Closes the sockets."""
        if self.rx_socket:
            self.rx_socket.close()
        if self.tx_socket:
            self.tx_socket.close()
        logging.info("X-Plane manager shut down.")


if __name__ == '__main__':
    import time

    logging.basicConfig(level=logging.INFO)

    def on_telemetry(data):
        # pass
        print(f"Received telemetry: {data.get('N')}, G-Force: {data.get('G', 0.0):.2f}")

    def on_event(event, *args):
        print(f"Received event: {event}, args: {args}")

    xp_manager = XPlaneManager(on_telemetry, on_event)
    xp_manager.start()

    # Example: send some axis data after a few seconds
    time.sleep(5)
    print("Sending example axis data...")
    xp_manager.set_override('joystick', True)
    xp_manager.send_axis_data({'jx': 0.5, 'jy': 0.1})

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
        xp_manager.quit()
        xp_manager.join()
        print("Exited.") 