# FSFFB - Hardware Tester

"""
Simple hardware tester for FSFFB.
This script tests the connection to the VPforce Rhino joystick and basic functionality.
"""

import time
import argparse
import logging

from fsffb.hardware.joystick_manager import JoystickManager

def main():
    print("\n--- FSFFB Hardware Tester ---")
    print("This will test your VPforce Rhino joystick connection and basic functionality.")
    print("Make sure your joystick is connected via USB.")
    print()
    
    # Initialize logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Create joystick manager
    joystick = JoystickManager()
    
    if not joystick.is_connected:
        print("❌ No VPforce Rhino joystick detected!")
        print("Please check:")
        print("1. USB connection")
        print("2. Device drivers")
        print("3. Device is powered on")
        return
    
    print("✅ VPforce Rhino joystick detected!")
    print(f"Device: {joystick.device_name}")
    print(f"Serial: {joystick.serial_number}")
    print()
    
    print("Testing basic functionality...")
    print("Move your joystick to see axis values, or press Ctrl+C to exit.")
    print()
    
    try:
        while True:
            # Read axes
            axes = joystick.read_axes()
            if axes:
                print(f"X: {axes.get('x', 0):6.3f} | Y: {axes.get('y', 0):6.3f} | Z: {axes.get('z', 0):6.3f} | R: {axes.get('r', 0):6.3f}", end='\r')
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n\nStopping test...")
    
    finally:
        joystick.close()
        print("✅ Hardware test completed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FSFFB Hardware Tester")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    main() 