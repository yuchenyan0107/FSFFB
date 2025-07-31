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
FFB Parameter Presets Manager

This module manages preset configurations for different aircraft types and
user-saved presets. It provides functionality to load, save, and manage
FFB parameter presets.
"""

import json
import os
import copy
import logging
from pathlib import Path

# Default aircraft-specific presets
DEFAULT_AIRCRAFT_PRESETS = {
        "172": {
        "name": "Cessna 172",
        "params": {
            'vne_override': 140,
            'aileron_expo': 25,
            'elevator_expo': 30,
            'stall_aoa_ratio': 90,
            'damper_coef': 8,
            'g_force_gain': 8,
            'elevator_droop_moment': 0,
            'wind_gain_x': 12,
            'wind_gain_y': 8,
            'wind_max_intensity': 15,
            'stick_shaker_intensity': 40,
            'runway_rumble_intensity': 10,
            'joystick_trim_follow_gain_physical_y': 50,
            'joystick_trim_follow_gain_virtual_y': 75,
            'joystick_trim_follow_gain_physical_x': 75,
            'joystick_trim_follow_gain_virtual_x': 75,
            'joystick_ap_follow_gain_physical_y': 40,
            'joystick_ap_follow_gain_physical_x': 40,
            'max_aileron_coeff': 100,
            'max_elevator_coeff': 100,
            'prop_diameter': 190,
        }
    },
        "A250": {
        "name": "Comanche A250",
        "params": {
            'vne_override': 310,
            'aileron_expo': 40,
            'elevator_expo': 45,
            'stall_aoa_ratio': 85,
            'damper_coef': 18,
            'g_force_gain': 14,
            'elevator_droop_moment': 2,
            'wind_gain_x': 14,
            'wind_gain_y': 10,
            'wind_max_intensity': 20,
            'stick_shaker_intensity': 65,
            'runway_rumble_intensity': 18,
            'joystick_trim_follow_gain_physical_y': 70,
            'joystick_trim_follow_gain_virtual_y': 90,
            'joystick_trim_follow_gain_physical_x': 90,
            'joystick_trim_follow_gain_virtual_x': 90,
            'joystick_ap_follow_gain_physical_y': 60,
            'joystick_ap_follow_gain_physical_x': 60,
            'max_aileron_coeff': 85,
            'max_elevator_coeff': 80,
            'prop_diameter': 220,
        }
    },

    "777": {
        "name": "Boeing 777",
        "description": "Heavy widebody airliner with moderate forces",
        "params": {
            'vne_override': 340,
            'aileron_expo': 45,
            'elevator_expo': 50,
            'stall_aoa_ratio': 85,
            'damper_coef': 15,
            'g_force_gain': 12,
            'elevator_droop_moment': 5,
            'wind_gain_x': 18,
            'wind_gain_y': 12,
            'wind_max_intensity': 25,
            'stick_shaker_intensity': 60,
            'runway_rumble_intensity': 15,
            'joystick_trim_follow_gain_physical_y': 65,
            'joystick_trim_follow_gain_virtual_y': 85,
            'joystick_trim_follow_gain_physical_x': 85,
            'joystick_trim_follow_gain_virtual_x': 85,
            'joystick_ap_follow_gain_physical_y': 55,
            'joystick_ap_follow_gain_physical_x': 55,
            'max_aileron_coeff': 90,
            'max_elevator_coeff': 85,
            'prop_diameter': 350,
        }
    },
    "737": {
        "name": "Boeing 737",
        "description": "Medium-haul narrow-body with crisp controls",
        "params": {
            'vne_override': 300,
            'aileron_expo': 35,
            'elevator_expo': 40,
            'stall_aoa_ratio': 80,
            'damper_coef': 12,
            'g_force_gain': 15,
            'elevator_droop_moment': 3,
            'wind_gain_x': 16,
            'wind_gain_y': 11,
            'wind_max_intensity': 22,
            'stick_shaker_intensity': 70,
            'runway_rumble_intensity': 20,
            'joystick_trim_follow_gain_physical_y': 60,
            'joystick_trim_follow_gain_virtual_y': 80,
            'joystick_trim_follow_gain_physical_x': 80,
            'joystick_trim_follow_gain_virtual_x': 80,
            'joystick_ap_follow_gain_physical_y': 50,
            'joystick_ap_follow_gain_physical_x': 50,
            'max_aileron_coeff': 95,
            'max_elevator_coeff': 90,
            'prop_diameter': 180,
        }
    },


    "Aerostar": {
        "name": "Aerostar",
        "params": {
            'vne_override': 800,
            'aileron_expo': 60,
            'elevator_expo': 65,
            'stall_aoa_ratio': 95,
            'damper_coef': 25,
            'g_force_gain': 25,
            'elevator_droop_moment': 0,
            'wind_gain_x': 20,
            'wind_gain_y': 15,
            'wind_max_intensity': 30,
            'stick_shaker_intensity': 80,
            'runway_rumble_intensity': 25,
            'joystick_trim_follow_gain_physical_y': 80,
            'joystick_trim_follow_gain_virtual_y': 95,
            'joystick_trim_follow_gain_physical_x': 95,
            'joystick_trim_follow_gain_virtual_x': 95,
            'joystick_ap_follow_gain_physical_y': 70,
            'joystick_ap_follow_gain_physical_x': 70,
            'max_aileron_coeff': 100,
            'max_elevator_coeff': 100,
            'prop_diameter': 100,
        }
    },
    "Cessna CitationX 750": {
        "name": "Cessna CitationX 750",
        "params": {
            'vne_override': 400,
            'aileron_expo': 30,
            'elevator_expo': 35,
            'stall_aoa_ratio': 88,
            'damper_coef': 10,
            'g_force_gain': 18,
            'elevator_droop_moment': 8,
            'wind_gain_x': 15,
            'wind_gain_y': 12,
            'wind_max_intensity': 25,
            'stick_shaker_intensity': 50,
            'runway_rumble_intensity': 30,
            'joystick_trim_follow_gain_physical_y': 45,
            'joystick_trim_follow_gain_virtual_y': 70,
            'joystick_trim_follow_gain_physical_x': 70,
            'joystick_trim_follow_gain_virtual_x': 70,
            'joystick_ap_follow_gain_physical_y': 30,
            'joystick_ap_follow_gain_physical_x': 30,
            'max_aileron_coeff': 100,
            'max_elevator_coeff': 100,
            'prop_diameter': 340,
        }
    },
    "C130": {
        "name": "C-130 Hercules",
        "description": "Military transport with heavy controls",
        "params": {
            'vne_override': 280,
            'aileron_expo': 50,
            'elevator_expo': 55,
            'stall_aoa_ratio': 82,
            'damper_coef': 20,
            'g_force_gain': 10,
            'elevator_droop_moment': 10,
            'wind_gain_x': 20,
            'wind_gain_y': 15,
            'wind_max_intensity': 30,
            'stick_shaker_intensity': 65,
            'runway_rumble_intensity': 35,
            'joystick_trim_follow_gain_physical_y': 70,
            'joystick_trim_follow_gain_virtual_y': 85,
            'joystick_trim_follow_gain_physical_x': 85,
            'joystick_trim_follow_gain_virtual_x': 85,
            'joystick_ap_follow_gain_physical_y': 55,
            'joystick_ap_follow_gain_physical_x': 55,
            'max_aileron_coeff': 85,
            'max_elevator_coeff': 80,
            'prop_diameter': 380,
        }
    },
    "CUSTOM": {
        "name": "Custom Settings",
        "description": "User-customizable preset",
        "params": {}  # Will be populated with current settings when saved
    }
}


class PresetManager:
    """Manages loading and saving of FFB parameter presets."""
    
    def __init__(self, user_presets_file="user_presets.json"):
        self.user_presets_file = user_presets_file
        self.user_presets = {}
        self.load_user_presets()
    
    def get_user_presets_path(self):
        """Get the path to user presets file."""
        # Store in the same directory as the application
        app_dir = Path(__file__).parent.parent.parent
        return app_dir / self.user_presets_file
    
    def load_user_presets(self):
        """Load user-saved presets from file."""
        presets_path = self.get_user_presets_path()
        try:
            if presets_path.exists():
                with open(presets_path, 'r') as f:
                    self.user_presets = json.load(f)
                logging.info(f"Loaded {len(self.user_presets)} user presets")
            else:
                logging.info("No user presets file found, starting with empty user presets")
                self.user_presets = {}
        except Exception as e:
            logging.error(f"Error loading user presets: {e}")
            self.user_presets = {}
    
    def save_user_presets(self):
        """Save user presets to file."""
        presets_path = self.get_user_presets_path()
        try:
            with open(presets_path, 'w') as f:
                json.dump(self.user_presets, f, indent=2)
            logging.info(f"Saved {len(self.user_presets)} user presets")
        except Exception as e:
            logging.error(f"Error saving user presets: {e}")
    
    def get_all_presets(self):
        """Get all available presets (default + user)."""
        all_presets = copy.deepcopy(DEFAULT_AIRCRAFT_PRESETS)
        all_presets.update(self.user_presets)
        return all_presets
    
    def get_preset_names(self):
        """Get list of all preset names for UI display."""
        return list(self.get_all_presets().keys())
    
    def get_preset(self, preset_name):
        """Get a specific preset by name."""
        all_presets = self.get_all_presets()
        return all_presets.get(preset_name)
    
    def save_user_preset(self, preset_name, params, description="User-saved preset"):
        """Save a user preset."""
        # Only save the 'value' from each parameter
        saved_params = {}
        for key, param_config in params.items():
            if isinstance(param_config, dict) and 'value' in param_config:
                saved_params[key] = param_config['value']
            else:
                saved_params[key] = param_config
        
        self.user_presets[preset_name] = {
            "name": preset_name,
            "description": description,
            "params": saved_params
        }
        self.save_user_presets()
        logging.info(f"Saved user preset: {preset_name}")
    
    def delete_user_preset(self, preset_name):
        """Delete a user preset."""
        if preset_name in self.user_presets:
            del self.user_presets[preset_name]
            self.save_user_presets()
            logging.info(f"Deleted user preset: {preset_name}")
            return True
        return False
    
    def apply_preset_to_params(self, preset_name, current_params):
        """Apply a preset to current parameters, returning updated params."""
        preset = self.get_preset(preset_name)
        if not preset:
            logging.error(f"Preset '{preset_name}' not found")
            return current_params
        
        updated_params = copy.deepcopy(current_params)
        preset_params = preset.get('params', {})
        
        for key, value in preset_params.items():
            if key in updated_params:
                updated_params[key]['value'] = value
            else:
                logging.warning(f"Preset parameter '{key}' not found in current parameters")
        
        logging.info(f"Applied preset: {preset['name']}")
        return updated_params


# Global preset manager instance
preset_manager = PresetManager() 