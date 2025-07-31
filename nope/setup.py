#!/usr/bin/env python3
"""
FSFFB Setup Script

This script provides easy installation and setup for the FSFFB application.
It handles dependency installation and environment setup.
"""

import sys
import subprocess
import os
import platform
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 9):
        print("❌ Error: Python 3.9 or higher is required.")
        print(f"Current version: {sys.version}")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True

def install_dependencies():
    """Install required dependencies."""
    print("\n📦 Installing dependencies...")
    
    # Core dependencies
    dependencies = [
        "PyQt6>=6.6.0",
        "numpy>=1.24.0", 
        "pyqtgraph>=0.13.0",
        "hidapi>=0.14.0",
        "simconnect>=0.1.0"
    ]
    
    for dep in dependencies:
        try:
            print(f"Installing {dep}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
            print(f"✅ {dep} installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {dep}: {e}")
            return False
    
    return True

def verify_installation():
    """Verify that all dependencies are properly installed."""
    print("\n🔍 Verifying installation...")
    
    try:
        import PyQt6
        print("✅ PyQt6 imported successfully")
    except ImportError:
        print("❌ PyQt6 import failed")
        return False
    
    try:
        import numpy
        print("✅ NumPy imported successfully")
    except ImportError:
        print("❌ NumPy import failed")
        return False
    
    try:
        import pyqtgraph
        print("✅ PyQtGraph imported successfully")
    except ImportError:
        print("❌ PyQtGraph import failed")
        return False
    
    try:
        import hid
        print("✅ HIDAPI imported successfully")
    except ImportError:
        print("❌ HIDAPI import failed")
        return False
    
    try:
        import simconnect
        print("✅ SimConnect imported successfully")
    except ImportError:
        print("❌ SimConnect import failed")
        return False
    
    return True

def create_launcher_script():
    """Create a launcher script for easy execution."""
    print("\n🚀 Creating launcher script...")
    
    if platform.system() == "Windows":
        launcher_content = """@echo off
cd /d "%~dp0"
python main.py %*
pause
"""
        launcher_file = "run_fsffb.bat"
    else:
        launcher_content = """#!/bin/bash
cd "$(dirname "$0")"
python main.py "$@"
"""
        launcher_file = "run_fsffb.sh"
    
    try:
        with open(launcher_file, 'w') as f:
            f.write(launcher_content)
        
        if platform.system() != "Windows":
            os.chmod(launcher_file, 0o755)
        
        print(f"✅ Launcher script created: {launcher_file}")
        return True
    except Exception as e:
        print(f"❌ Failed to create launcher script: {e}")
        return False

def main():
    """Main setup function."""
    print("🎮 FSFFB Setup")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print("\n❌ Dependency installation failed. Please check the error messages above.")
        sys.exit(1)
    
    # Verify installation
    if not verify_installation():
        print("\n❌ Installation verification failed. Please check the error messages above.")
        sys.exit(1)
    
    # Create launcher script
    create_launcher_script()
    
    print("\n🎉 FSFFB setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Connect your VPforce Rhino joystick")
    print("2. Start your flight simulator (MSFS or X-Plane)")
    print("3. Run the application:")
    print("   - Windows: double-click run_fsffb.bat")
    print("   - Linux/Mac: ./run_fsffb.sh")
    print("   - Or manually: python main.py [msfs|xplane]")
    print("\n📖 For more information, see INSTALL.md")

if __name__ == "__main__":
    main() 