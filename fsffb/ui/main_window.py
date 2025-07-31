#
# This program is largely based on the TelemFFB distribution (https://github.com/walmis/TelemFFB).
#

import sys
import numpy as _np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QLabel, QSlider, QCheckBox, QTextEdit, QScrollArea, QFrame,
    QGroupBox, QSplitter, QPushButton, QInputDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from .widgets import FourQuadrantPlot
from ..core.aircraft import get_available_presets, get_preset_info, save_current_as_preset

class MainWindow(QMainWindow):
    """The main application window."""
    parameter_changed = pyqtSignal(str, object) # name, value
    preset_load_requested = pyqtSignal(str) # preset_name
    preset_save_requested = pyqtSignal(str, str) # preset_name, description

    def __init__(self, params_config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FSFFB Control Panel")
        self.setGeometry(100, 100, 1600, 800)  # Made wider to accommodate presets
        self.params_config = params_config
        self.controls = {}

        # --- Define the list of telemetry keys you want to see ---
        # You can easily add or remove items from this list to customize the display.
        self.telemetry_keys_to_display = [
            # Flight Dynamics
            "G",  "AccBody",
            "IAS", "AoA", "SideSlip", "VelRotBody", "Pitch", "Roll",
            "StallAoA", "DynPressure","AirDensity",

            # Control Surfaces
            "ElevDefl", "ElevDeflPct","AileronDefl", "AileronDeflPctLR", "RudderDefl",
            # Trim
            "ElevTrim", "ElevTrimPct", "AileronTrim",

            #"ElevTrimUpLmt", "ElevTrimDnLmt", "ElevTrimNeutral",

            # State
            #"SimOnGround", "Parked", "EngineType"

            "TAS",

            "APMaster",
            
            # Stick Forces from X-Plane
            #"StickForcePitch", "StickForceRoll", "StickForceYaw",

            "PropThrust"
        ]

        # --- Main Layout ---
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout()
        main_widget.setLayout(main_layout)

        # --- Left Panel: Controls ---
        controls_scroll = QScrollArea()
        controls_scroll.setWidgetResizable(True)
        controls_panel = QWidget()
        self.controls_layout = QVBoxLayout(controls_panel)
        controls_scroll.setWidget(controls_panel)

        # --- Middle-Left Panel: Presets ---
        presets_panel = QWidget()
        presets_layout = QVBoxLayout(presets_panel)
        presets_layout.addWidget(QLabel("<h2>Presets</h2>"))
        
        # Create preset buttons
        self.preset_buttons_layout = QVBoxLayout()
        presets_layout.addLayout(self.preset_buttons_layout)
        presets_layout.addStretch()

        # --- Middle Panel: Plots ---
        plots_panel = QWidget()
        plots_layout = QGridLayout(plots_panel)

        # --- Right Panel: Telemetry ---
        telemetry_panel = QWidget()
        telemetry_layout = QVBoxLayout(telemetry_panel)
        
        # Create a splitter for the telemetry section
        telemetry_splitter = QSplitter(Qt.Orientation.Vertical)
        telemetry_layout.addWidget(telemetry_splitter)
        
        main_layout.addWidget(controls_scroll, 1)
        main_layout.addWidget(presets_panel, 0)  # Fixed width for presets
        main_layout.addWidget(plots_panel, 2)
        main_layout.addWidget(telemetry_panel, 1)

        # --- Populate Controls, Presets, Plots, and Telemetry ---
        self._populate_controls()
        self._populate_presets()
        self._populate_plots(plots_layout)
        self._populate_telemetry(telemetry_splitter)
        self._populate_debug_info(telemetry_splitter)
        
        # Set initial splitter proportions (60% telemetry, 40% debug)
        telemetry_splitter.setSizes([600, 400])

    def _populate_controls(self):
        """Dynamically creates UI controls from the params config."""
        self.controls_layout.addWidget(QLabel("<h2>FFB Parameters</h2>"))
        
        for name, config in self.params_config.items():
            
            if config['type'] == 'slider':
                # Use a horizontal layout for sliders to include a value label
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)

                label = QLabel(config['label'])
                slider = QSlider(Qt.Orientation.Horizontal)
                value_label = QLabel(str(config['value']))
                value_label.setFixedWidth(40) # Ensure consistent width

                slider.setRange(config['min'], config['max'])
                slider.setValue(config['value'])
                
                # Connect signals
                slider.valueChanged.connect(lambda val, n=name: self.parameter_changed.emit(n, val))
                slider.valueChanged.connect(lambda val, lbl=value_label: lbl.setText(str(val)))

                row_layout.addWidget(label)
                row_layout.addWidget(slider)
                row_layout.addWidget(value_label)

                self.controls[name] = slider
                self.controls_layout.addWidget(row)
            
            elif config['type'] == 'checkbox':
                # Checkboxes are simpler and don't need a separate row layout
                checkbox = QCheckBox(config['label'])
                checkbox.setChecked(config['value'])
                checkbox.stateChanged.connect(lambda state, n=name: self.parameter_changed.emit(n, bool(state)))
                self.controls[name] = checkbox
                self.controls_layout.addWidget(checkbox)
            
            # Add a small separator line
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setFrameShadow(QFrame.Shadow.Sunken)
            self.controls_layout.addWidget(line)
        
        self.controls_layout.addStretch()

    def _populate_presets(self):
        """Creates preset load/save buttons."""
        preset_names = get_available_presets()
        
        for preset_name in preset_names:
            preset_info = get_preset_info(preset_name)
            display_name = preset_info.get('name', preset_name) if preset_info else preset_name
            
            # Create a horizontal layout for each preset
            preset_row = QWidget()
            preset_row_layout = QHBoxLayout(preset_row)
            preset_row_layout.setContentsMargins(2, 2, 2, 2)
            
            # Large load button
            load_btn = QPushButton(display_name)
            load_btn.setMinimumHeight(30)
            load_btn.clicked.connect(lambda checked, name=preset_name: self.load_preset(name))
            
            # Small save button
            save_btn = QPushButton("S")
            save_btn.setMaximumWidth(25)
            save_btn.setMinimumHeight(30)
            save_btn.setToolTip(f"Save current settings as '{display_name}'")
            save_btn.clicked.connect(lambda checked, name=preset_name: self.save_preset(name))
            
            preset_row_layout.addWidget(load_btn, 3)  # 3/4 of the space
            preset_row_layout.addWidget(save_btn, 1)  # 1/4 of the space
            
            self.preset_buttons_layout.addWidget(preset_row)
        
        # Add a "New Preset" button at the bottom
        new_preset_btn = QPushButton("+ New Preset")
        new_preset_btn.clicked.connect(self.create_new_preset)
        self.preset_buttons_layout.addWidget(new_preset_btn)

    def load_preset(self, preset_name):
        """Load a preset and update UI controls."""
        self.preset_load_requested.emit(preset_name)
        
    def save_preset(self, preset_name):
        """Save current parameters to a preset."""
        preset_info = get_preset_info(preset_name)
        if preset_info:
            display_name = preset_info.get('name', preset_name)
            description = preset_info.get('description', f"Updated {display_name}")
        else:
            display_name = preset_name
            description = f"User preset {preset_name}"
        
        self.preset_save_requested.emit(preset_name, description)
        QMessageBox.information(self, "Preset Saved", f"Current settings saved to '{display_name}'")
        
    def create_new_preset(self):
        """Create a new user preset."""
        preset_name, ok = QInputDialog.getText(
            self, 
            'New Preset', 
            'Enter preset name:'
        )
        
        if ok and preset_name.strip():
            preset_name = preset_name.strip()
            description, ok2 = QInputDialog.getText(
                self,
                'Preset Description',
                'Enter description (optional):',
                text=f"Custom preset: {preset_name}"
            )
            
            if ok2:
                self.preset_save_requested.emit(preset_name, description)
                QMessageBox.information(self, "Preset Created", f"New preset '{preset_name}' created")
                # Refresh the preset buttons
                self._refresh_presets()

    def _refresh_presets(self):
        """Refresh the preset buttons list."""
        # Clear existing preset buttons
        while self.preset_buttons_layout.count():
            child = self.preset_buttons_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Repopulate
        self._populate_presets()

    def update_controls_from_params(self, new_params):
        """Update UI controls when parameters change (e.g., from preset loading)."""
        for name, config in new_params.items():
            if name in self.controls:
                control = self.controls[name]
                value = config.get('value', config.get('min', 0))
                
                if isinstance(control, QSlider):
                    control.setValue(int(value))
                elif isinstance(control, QCheckBox):
                    control.setChecked(bool(value))

    def _populate_plots(self, layout):
        self.plot_joystick_phys = FourQuadrantPlot("Physical Joystick Position")
        self.plot_force_offsets = FourQuadrantPlot("Trim/AP Force Offsets")
        self.plot_constant_force = FourQuadrantPlot("Constant Force Vector")
        self.plot_sim_axes = FourQuadrantPlot("Simulator Axis Output")
        
        layout.addWidget(self.plot_joystick_phys, 0, 0)
        layout.addWidget(self.plot_force_offsets, 0, 1)
        layout.addWidget(self.plot_constant_force, 1, 0)
        layout.addWidget(self.plot_sim_axes, 1, 1)

    def _populate_telemetry(self, splitter):
        """Creates the live telemetry display section."""
        telemetry_widget = QWidget()
        telemetry_layout = QVBoxLayout(telemetry_widget)
        
        telemetry_layout.addWidget(QLabel("<h2>Live Telemetry</h2>"))
        self.telemetry_display = QTextEdit()
        self.telemetry_display.setReadOnly(True)
        self.telemetry_display.setFontFamily("Courier")
        telemetry_layout.addWidget(self.telemetry_display)
        
        splitter.addWidget(telemetry_widget)

    def _populate_debug_info(self, splitter):
        """Creates a section to display internal FFB calculator values."""
        debug_widget = QWidget()
        debug_layout = QVBoxLayout(debug_widget)
        
        debug_group = QGroupBox("FFB Calculator Internals")
        self.debug_layout = QGridLayout()
        debug_group.setLayout(self.debug_layout)

        # Initialize with empty labels dictionary - will be populated dynamically
        self.debug_labels = {}
        self.debug_label_widgets = {}  # Store both label and value widgets
        
        debug_layout.addWidget(debug_group)
        debug_layout.addStretch()
        
        splitter.addWidget(debug_widget)

    def _update_debug_labels(self, data):
        """Dynamically creates or updates debug labels based on available data."""
        # Clear existing layout
        while self.debug_layout.count():
            child = self.debug_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Create new labels for all data keys
        row = 0
        for key, value in data.items():
            # Create label widget
            label_widget = QLabel(f"{key.replace('_', ' ').title()}:")
            value_widget = QLabel("...")
            
            # Store widgets for later updates
            self.debug_labels[key] = value_widget
            self.debug_label_widgets[key] = (label_widget, value_widget)
            
            # Add to layout
            self.debug_layout.addWidget(label_widget, row, 0)
            self.debug_layout.addWidget(value_widget, row, 1)
            row += 1
        
    def update_debug_display(self, data):
        """Updates the debug labels with new data from the calculator."""
        # If this is the first time or new keys were added, recreate the layout
        if not self.debug_labels or set(data.keys()) != set(self.debug_labels.keys()):
            self._update_debug_labels(data)
        
        # Update all existing labels
        for key, label in self.debug_labels.items():
            value = data.get(key, 'N/A')
            if isinstance(value, float):
                label.setText(f"{value:.4f}")
            else:
                label.setText(str(value))

    def update_telemetry_display(self, data):
        """Updates the telemetry text display with a curated list of data."""
        text = ""
        for key in self.telemetry_keys_to_display:
            value = data.get(key) # Use .get() to handle missing keys gracefully
            if value is None:
                continue # Skip keys not present in the current data packet
            
            if isinstance(value, list):
                # Format lists nicely
                value_str = ", ".join([f"{v:.2f}" for v in value])
                text += f"{key:<25}: [{value_str}]\n"
            elif isinstance(value, (int, float)):
                text += f"{key:<25}: {value:.3f}\n"
            else:
                text += f"{key:<25}: {value}\n"
        self.telemetry_display.setPlainText(text)

    def update_plots(self, joystick_axes, offsets, const_force, sim_axes):
        """Updates all the plot widgets with new data."""
        self.plot_joystick_phys.update_point(joystick_axes.get('jx', 0), -joystick_axes.get('jy', 0))
        self.plot_force_offsets.update_point(offsets.get('x', 0), offsets.get('y', 0))
        
        mag = const_force.get('magnitude', 0)
        direction_rad = const_force.get('direction', 0) * (_np.pi / 180.0)
        const_x = mag * _np.cos(direction_rad)
        const_y = mag * _np.sin(direction_rad)
        self.plot_constant_force.update_point(-const_x, -const_y)
        
        self.plot_sim_axes.update_point(-sim_axes.get('jx', 0), sim_axes.get('jy', 0))


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Example params_config (replace with actual config)
    params_config = {
        'g_force_gain': {'label': 'G-Force Gain', 'type': 'slider', 'min': 0, 'max': 100, 'value': 50},
        'ap_follow_enabled': {'label': 'Enable AP Following', 'type': 'checkbox', 'value': True},
        'constant_force_magnitude': {'label': 'Constant Force Magnitude', 'type': 'slider', 'min': 0, 'max': 100, 'value': 50},
        'constant_force_direction': {'label': 'Constant Force Direction (degrees)', 'type': 'slider', 'min': 0, 'max': 360, 'value': 0},
    }
    window = MainWindow(params_config)
    window.show()
    sys.exit(app.exec()) 