#!/usr/bin/env python3
"""
Test script to verify FSFFB imports work correctly.
"""

import sys
import os

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test all the main imports to ensure they work with the new naming."""
    try:
        print("Testing FSFFB imports...")
        
        # Test main package import
        import fsffb
        print("✅ fsffb package imported successfully")
        
        # Test core modules
        from fsffb.core import aircraft, ffb_calculator, presets
        print("✅ fsffb.core modules imported successfully")
        
        # Test hardware modules
        from fsffb.hardware import joystick_manager, simulator_controller
        print("✅ fsffb.hardware modules imported successfully")
        
        # Test telemetry modules
        from fsffb.telemetry import msfs_manager, xplane_manager
        print("✅ fsffb.telemetry modules imported successfully")
        
        # Test UI modules
        from fsffb.ui import main_window, widgets
        print("✅ fsffb.ui modules imported successfully")
        
        # Test utilities
        from fsffb import utils
        print("✅ fsffb.utils imported successfully")
        
        print("\n🎉 All FSFFB imports successful!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1) 