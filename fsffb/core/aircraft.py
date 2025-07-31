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
Aircraft Module

This module manages aircraft-specific parameters that are used for FFB calculations.
It now includes integration with the preset system for easy parameter management.
"""

import copy
from .presets import preset_manager

# This is the central definition for all tunable FFB parameters.
# The UI will be generated dynamically from this structure.
# To add a new parameter:
# 1. Add it to this dictionary with its properties (label, type, range, default value).
# 2. Use it in ffb_calculator.py by accessing `self.params['your_param_name']['value']`.
DEFAULT_AIRCRAFT_PARAMS = {
    # --- Aerodynamics ---
    
    'vne_override': {'label': 'Vne Override (kts)', 'type': 'slider', 'min': 0, 'max': 400, 'value': 120},
    'aileron_expo': {'label': 'Aileron Force Expo', 'type': 'slider', 'min': -100, 'max': 100, 'value': 40},
    'elevator_expo': {'label': 'Elevator Force Expo', 'type': 'slider', 'min': -100, 'max': 100, 'value': 40},
    

    'stall_aoa_ratio': {'label': 'Stall AoA Multiplier', 'type': 'slider', 'min': 0, 'max': 100, 'value': 85},

    'damper_coef': {'label': 'Damper Coef', 'type': 'slider', 'min': 0, 'max': 100, 'value': 10},
    
    # --- Constant Forces ---
    'g_force_gain': {'label': 'G-Force Gain', 'type': 'slider', 'min': 0, 'max': 100, 'value': 10},
    'elevator_droop_moment': {'label': 'Elevator Droop', 'type': 'slider', 'min': 0, 'max': 100, 'value': 0},

    'wind_gain_x': {'label': 'Wind Gain Roll', 'type': 'slider', 'min': -30, 'max': 30, 'value': 15},
    'wind_gain_y': {'label': 'Wind Gain Pitch', 'type': 'slider', 'min': -30, 'max': 30, 'value': 10},

    'wind_max_intensity': {'label': 'Wind Max Intensity', 'type': 'slider', 'min': 0, 'max': 50, 'value': 20},

    # --- Vibrations & Other Effects ---
    'enable_stick_shaker': {'label': 'Enable Stick Shaker', 'type': 'checkbox', 'value': True},
    'stick_shaker_intensity': {'label': 'Stick Shaker Intensity', 'type': 'slider', 'min': 0, 'max': 100, 'value': 50},
    'runway_rumble_intensity': {'label': 'Runway Rumble Intensity', 'type': 'slider', 'min': 0, 'max': 100, 'value': 0},

    # --- Trim & Autopilot ---
    
    'trim_following': {'label': 'Enable Trim Following', 'type': 'checkbox', 'value': True},
    'joystick_trim_follow_gain_physical_y': {'label': 'Y Trim Physical', 'type': 'slider', 'min': 0, 'max': 100, 'value': 58},
    'joystick_trim_follow_gain_virtual_y': {'label': 'Y Trim Virtual', 'type': 'slider', 'min': 0, 'max': 100, 'value': 80},
    'joystick_trim_follow_gain_physical_x': {'label': 'X Trim Physical', 'type': 'slider', 'min': 0, 'max': 100, 'value': 80},
    'joystick_trim_follow_gain_virtual_x': {'label': 'X Trim Virtual', 'type': 'slider', 'min': 0, 'max': 100, 'value': 80},

    

    'ap_following': {'label': 'Enable AP Following', 'type': 'checkbox', 'value': True},
    'ap_trim_only': {'label': 'AP Trim Only', 'type': 'checkbox', 'value': False},
    'PMDG_AP_On': {'label': 'PMDG AP On', 'type': 'checkbox', 'value': False},
    'joystick_ap_follow_gain_physical_y': {'label': 'Y AP Physical', 'type': 'slider', 'min': 0, 'max': 100, 'value': 50},
    'joystick_ap_follow_gain_physical_x': {'label': 'X AP Physical', 'type': 'slider', 'min': 0, 'max': 100, 'value': 50},

    'send_stick_position': {'label': 'Send Stick Position to Game', 'type': 'checkbox', 'value': True},

    'max_aileron_coeff': {'label': 'Max Aileron Force %', 'type': 'slider', 'min': 0, 'max': 100, 'value': 100},
    'max_elevator_coeff': {'label': 'Max Elevator Force %', 'type': 'slider', 'min': 0, 'max': 100, 'value': 100},
    'prop_diameter': {'label': 'Prop Diameter (cm)', 'type': 'slider', 'min': 1, 'max': 500, 'value': 190},
    
    # --- FFB Control ---
    
    
    'test1': {'label': 'test1', 'type': 'checkbox', 'value': False},
    'test2': {'label': 'test2', 'type': 'checkbox', 'value': False},
    

}


def get_aircraft_params(aircraft_name="default", preset_name=None):
    """
    Returns a dictionary of parameters for a given aircraft.
    
    Args:
        aircraft_name: Name of the aircraft (for future use)
        preset_name: Name of the preset to load (if specified)
    
    Returns:
        Dictionary of parameter configurations
    """
    # Start with default parameters
    params = copy.deepcopy(DEFAULT_AIRCRAFT_PARAMS)
    
    # If a preset is specified, apply it
    if preset_name and preset_name != "default":
        params = preset_manager.apply_preset_to_params(preset_name, params)
    
    return params

def get_available_presets():
    """Get list of available preset names."""
    return preset_manager.get_preset_names()

def get_preset_info(preset_name):
    """Get detailed information about a preset."""
    return preset_manager.get_preset(preset_name)

def save_current_as_preset(preset_name, current_params, description="User-saved preset"):
    """Save current parameters as a new preset."""
    preset_manager.save_user_preset(preset_name, current_params, description)

if __name__ == '__main__':
    # Example Usage
    ac_name = "Generic Fighter"
    params = get_aircraft_params(ac_name)
    print(f"Parameters for {ac_name}:")
    # Access a value
    print(f"  G-Force Gain: {params['g_force_gain']['value']}") 