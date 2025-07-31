# FSFFB Installation Guide

## Overview
FSFFB is a force feedback system for flight simulators that provides realistic control forces based on aircraft telemetry data. This guide covers installation for the FSFFB application.

## System Requirements

### Minimum Requirements
- **OS**: Windows 10/11 (64-bit)
- **Python**: 3.9 or higher
- **RAM**: 4GB
- **Storage**: 500MB free space
- **Hardware**: VPforce Rhino or compatible force feedback joystick

### Recommended Requirements
- **OS**: Windows 11 (64-bit)
- **Python**: 3.11 or higher
- **RAM**: 8GB or more
- **Storage**: 1GB free space
- **Hardware**: VPforce Rhino with latest firmware

## Installation Methods

### Method 1: Using Conda (Recommended)

1. **Install Miniconda or Anaconda**
   ```bash
   # Download and install Miniconda from: https://docs.conda.io/en/latest/miniconda.html
   ```

2. **Create a new conda environment**
   ```bash
   conda create -n fsffb python=3.11
   conda activate fsffb
   ```

3. **Install core dependencies**
   ```bash
   conda install -c conda-forge numpy pyqtgraph
   conda install -c conda-forge pyqt
   ```

4. **Install additional dependencies**
   ```bash
   pip install hidapi simconnect
   ```

5. **Verify installation**
   ```bash
   python -c "import PyQt6, numpy, pyqtgraph, hid, simconnect; print('All dependencies installed successfully!')"
   ```

### Method 2: Using pip (Alternative)

1. **Ensure Python 3.9+ is installed**
   ```bash
   python --version
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv fsffb_env
   # On Windows:
   fsffb_env\Scripts\activate
   # On Linux/Mac:
   source fsffb_env/bin/activate
   ```

3. **Install all dependencies**
   ```bash
   pip install -r requirements.txt
   ```

### Method 3: Manual Installation

If you encounter issues with the above methods, you can install dependencies manually:

```bash
# Core GUI framework
pip install PyQt6>=6.6.0

# Scientific computing
pip install numpy>=1.24.0

# Data visualization
pip install pyqtgraph>=0.13.0

# Hardware interface
pip install hidapi>=0.14.0

# Microsoft Flight Simulator integration
pip install simconnect>=0.1.0
```

## Hardware Setup

### VPforce Rhino Setup
1. **Connect the device** via USB
2. **Install drivers** if prompted by Windows
3. **Verify device detection**:
   ```bash
   python hardware_tester.py
   ```

### Flight Simulator Setup
1. **Microsoft Flight Simulator 2020/2024**:
   - Ensure SimConnect is enabled
   - No additional setup required

2. **X-Plane**:
   - Install the provided X-Plane plugin
   - Enable the plugin in X-Plane settings

## Running FSFFB

### Basic Usage
```bash
# Navigate to the FSFFB-Refactored directory
cd FSFFB-Refactored

# Run with Microsoft Flight Simulator
python main.py msfs

# Run with X-Plane
python main.py xplane
```

### Command Line Options
```bash
python main.py [simulator]
```
- `msfs`: Microsoft Flight Simulator (default)
- `xplane`: X-Plane

### GUI Features
- **FFB Parameters**: Adjust force feedback settings in real-time
- **Presets**: Load aircraft-specific configurations
- **Live Telemetry**: Monitor aircraft data
- **Debug Information**: View internal calculations
- **Real-time Plots**: Visualize joystick position and forces

## Troubleshooting

### Common Issues

1. **"No module named 'hid'"**
   ```bash
   pip install hidapi
   ```

2. **"No module named 'simconnect'"**
   ```bash
   pip install simconnect
   ```

3. **Joystick not detected**
   - Check USB connection
   - Verify device drivers
   - Run `python hardware_tester.py`

4. **SimConnect connection failed**
   - Ensure MSFS is running
   - Check firewall settings
   - Verify SimConnect is enabled in MSFS

5. **PyQt6 import errors**
   ```bash
   conda install -c conda-forge pyqt
   # or
   pip install PyQt6
   ```

### Performance Issues

1. **High CPU usage**:
   - Reduce telemetry update frequency
   - Close unnecessary applications
   - Check for background processes

2. **Force feedback lag**:
   - Ensure joystick is properly connected
   - Check USB port (use USB 3.0 if available)
   - Verify firmware is up to date

### Debug Mode

Enable detailed logging:
```bash
python main.py msfs --debug
```

## Development Setup

### For Contributors
1. **Clone the repository**
   ```bash
   git clone https://github.com/walmis/FSFFB.git
   cd FSFFB/FSFFB-Refactored
   ```

2. **Install development dependencies**
   ```bash
   pip install pytest black flake8
   ```

3. **Run tests**
   ```bash
   pytest tests/
   ```

4. **Format code**
   ```bash
   black fsffb/
   ```

## Support

### Getting Help
- **GitHub Issues**: Report bugs and feature requests
- **Documentation**: Check the README.md file
- **Community**: Join the Discord server

### Logs
Logs are stored in the application directory. Check for:
- `fsffb.log`: Main application log
- `user_presets.json`: User-saved presets

## License
FSFFB is licensed under the GNU General Public License v3.0.
See the COPYING.txt file for details. 