import sys
import json
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QSlider, QLabel, QInputDialog, QColorDialog,
    QGroupBox, QGridLayout, QScrollArea, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

# Use the 'QtAgg' backend for matplotlib to integrate with PyQt
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# A custom button widget for the color swatch in the sample list
class ColorButton(QPushButton):
    """A button that displays a solid color."""
    def __init__(self, color, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFixedSize(20, 20)
        self._color = QColor(color)
        self.setStyleSheet(f"background-color: {self._color.name()}; border: 1px solid black;")

    def set_color(self, color):
        self._color = QColor(color)
        self.setStyleSheet(f"background-color: {self._color.name()}; border: 1px solid black;")

# The main application window
class SpiderChartApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Arachgraph Spider Graph Generator")
        self.setGeometry(100, 100, 1200, 800)

        # --- Data Storage ---
        self.factors = []
        self.samples = {}  # { "sample_name": {"color": "#hex", "values": [...], "ui_widget": QWidget}}
        self.factor_controls = {}  # { "factor_name": {"slider": QSlider, ...}}

        # --- UI Setup ---
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QGridLayout(self.central_widget)

        self.init_ui()
        self._update_chart() # Initial draw

    def init_ui(self):
        """Initializes the main UI layout and widgets."""
        # --- Left Panel: Samples List ---
        sample_list_group = QGroupBox("Samples")
        self.sample_list_layout = QVBoxLayout()
        self.sample_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        sample_list_group.setLayout(self.sample_list_layout)
        self.main_layout.addWidget(sample_list_group, 0, 0)
        
        # --- Center Panel: Chart ---
        self.canvas = MplCanvas(self, width=6, height=6, dpi=100)
        self.main_layout.addWidget(self.canvas, 0, 1, 2, 1) # Span 2 rows
        
        # --- Bottom Left Panel: Factor Controls ---
        factor_group = QGroupBox("Factor Controls")
        factor_scroll_area = QScrollArea()
        factor_scroll_area.setWidgetResizable(True)
        factor_scroll_content = QWidget()
        self.factor_layout = QVBoxLayout(factor_scroll_content)
        self.factor_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        factor_scroll_area.setWidget(factor_scroll_content)
        factor_group_layout = QVBoxLayout()
        factor_group_layout.addWidget(factor_scroll_area)
        factor_group.setLayout(factor_group_layout)
        self.main_layout.addWidget(factor_group, 1, 0)

        # --- Bottom Panel: Action Buttons ---
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.btn_load_factors = QPushButton("Load Factors")
        self.btn_load_factors.clicked.connect(self.load_factors)
        
        self.btn_load_sample = QPushButton("Load Sample")
        self.btn_load_sample.clicked.connect(self.load_sample)
        
        self.btn_add_sample = QPushButton("Add Sample to chart")
        self.btn_add_sample.clicked.connect(self.add_sample)
        self.btn_add_sample.setEnabled(False) # Disabled until factors are loaded

        self.btn_save_sample = QPushButton("Save Sample")
        self.btn_save_sample.clicked.connect(self.save_sample)
        self.btn_save_sample.setEnabled(False) # Disabled until samples exist

        button_layout.addWidget(self.btn_load_factors)
        button_layout.addWidget(self.btn_load_sample)
        button_layout.addWidget(self.btn_add_sample)
        button_layout.addWidget(self.btn_save_sample)
        
        self.main_layout.addWidget(button_widget, 2, 0, 1, 2) # Span 2 columns

        # Adjust layout proportions
        self.main_layout.setColumnStretch(0, 1) # Left column (controls)
        self.main_layout.setColumnStretch(1, 2) # Right column (chart)
        self.main_layout.setRowStretch(0, 1)
        self.main_layout.setRowStretch(1, 1)

    # --- Core Functionality Methods ---
    
    def load_factors(self):
        """Opens a file dialog to load factors from a JSON file."""
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Factor File", "", "JSON Files (*.json)")
        if not filepath: return

        try:
            with open(filepath, 'r') as f:
                loaded_factors = json.load(f)
                if not all("name" in item and "description" in item for item in loaded_factors):
                    raise ValueError("Each factor must have a 'name' and 'description'.")
        except (json.JSONDecodeError, ValueError, IOError) as e:
            QMessageBox.critical(self, "Error", f"Failed to load or parse factor file:\n{e}")
            return

        self._clear_all()
        self.factors = loaded_factors
        self._setup_ui_for_factors()
        self._update_chart()
        self.btn_add_sample.setEnabled(True)

    def add_sample(self):
        """Prompts for a sample name and adds the current slider values to the chart."""
        name, ok = QInputDialog.getText(self, "Add Sample", "Enter sample name:")
        if not (ok and name): return
        if name in self.samples:
            QMessageBox.warning(self, "Duplicate Name", "A sample with this name already exists.")
            return
            
        values = [self.factor_controls[f['name']]['slider'].value() for f in self.factors]
        
        # Cycle through a list of default colors for new samples
        default_colors = ["#34a853", "#4285f4", "#fbbc05", "#ea4335", "#9c27b0", "#00bcd4"]
        color = default_colors[len(self.samples) % len(default_colors)]

        self.samples[name] = {"values": values, "color": color}
        self._add_sample_to_list_ui(name, color)
        self._update_chart()
        self.btn_save_sample.setEnabled(True)

    def save_sample(self):
        """Saves a selected sample's data to a JSON file."""
        if not self.samples: return

        sample_to_save, ok = QInputDialog.getItem(self, "Save Sample", 
            "Select sample to save:", list(self.samples.keys()), 0, False)
        if not (ok and sample_to_save): return
            
        sample_data = self.samples[sample_to_save]
        output_data = {
            "name": sample_to_save,
            "color": sample_data["color"],
            "values": {self.factors[i]['name']: val for i, val in enumerate(sample_data['values'])}
        }
            
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Sample File", f"{sample_to_save}.json", "JSON Files (*.json)")
        if filepath:
            try:
                with open(filepath, 'w') as f:
                    json.dump(output_data, f, indent=4)
            except IOError as e:
                QMessageBox.critical(self, "Error", f"Could not save file:\n{e}")

    def load_sample(self):
        """Loads a sample from a JSON file and adds it to the chart."""
        if not self.factors:
            QMessageBox.information(self, "Information", "Please load factors before loading a sample.")
            return

        filepath, _ = QFileDialog.getOpenFileName(self, "Load Sample File", "", "JSON Files (*.json)")
        if not filepath: return

        try:
            with open(filepath, 'r') as f: data = json.load(f)
            if not all(k in data for k in ["name", "values", "color"]):
                raise ValueError("Sample file is missing required keys: name, values, color.")
            
            if set(data['values'].keys()) != {f['name'] for f in self.factors}:
                raise ValueError("Sample factors do not match currently loaded factors.")

        except (json.JSONDecodeError, ValueError, IOError) as e:
            QMessageBox.critical(self, "Error", f"Failed to load sample file:\n{e}")
            return
        
        name = data['name']
        if name in self.samples:
            QMessageBox.warning(self, "Duplicate Name", f"A sample named '{name}' already exists.")
            return
            
        # Order values correctly according to the current factor list
        values = [data['values'][f['name']] for f in self.factors]
        self.samples[name] = {"values": values, "color": data['color']}
        self._add_sample_to_list_ui(name, data['color'])
        self._update_chart()
        self.btn_save_sample.setEnabled(True)

    def change_sample_color(self, sample_name):
        """Opens a color dialog to change a sample's color."""
        current_color = QColor(self.samples[sample_name]['color'])
        new_color = QColorDialog.getColor(current_color, self, "Select Color")

        if new_color.isValid():
            color_hex = new_color.name()
            self.samples[sample_name]['color'] = color_hex
            self.samples[sample_name]['ui_color_btn'].set_color(color_hex)
            self._update_chart()

    # --- UI Helper Methods ---
    
    def _clear_all(self):
        """Resets the application state and UI elements."""
        self.factors, self.samples, self.factor_controls = [], {}, {}
        
        for layout in [self.factor_layout, self.sample_list_layout]:
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
        
        self.btn_save_sample.setEnabled(False)
        self.btn_add_sample.setEnabled(False)

    def _setup_ui_for_factors(self):
        """Dynamically creates sliders and labels for each loaded factor."""
        for factor in self.factors:
            name, description = factor['name'], factor['description']
            factor_box = QGroupBox(name)
            factor_box.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            
            desc_label = QLabel(description)
            desc_label.setWordWrap(True)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(1, 10)
            slider.setValue(5)
            slider.setTickPosition(QSlider.TickPosition.TicksBelow)
            value_label = QLabel("5")
            value_label.setFixedWidth(20)
            slider.valueChanged.connect(lambda val, lbl=value_label: lbl.setText(str(val)))
            
            slider_layout = QHBoxLayout()
            slider_layout.addWidget(slider)
            slider_layout.addWidget(value_label)
            box_layout = QVBoxLayout(factor_box)
            box_layout.addWidget(desc_label)
            box_layout.addLayout(slider_layout)
            self.factor_layout.addWidget(factor_box)

            self.factor_controls[name] = {"slider": slider, "value_label": value_label}

    def _add_sample_to_list_ui(self, name, color_hex):
        """Adds a new entry to the sample list UI."""
        sample_widget = QWidget()
        layout = QHBoxLayout(sample_widget)
        layout.setContentsMargins(0, 5, 0, 5)
        
        color_btn = ColorButton(color_hex)
        color_btn.clicked.connect(lambda: self.change_sample_color(name))
        layout.addWidget(color_btn)
        layout.addWidget(QLabel(name))
        layout.addStretch()

        self.sample_list_layout.addWidget(sample_widget)
        self.samples[name]["ui_color_btn"] = color_btn

    def _update_chart(self):
        """Clears and redraws the entire spider chart."""
        self.canvas.ax.clear()
        
        if not self.factors:
            self.canvas.ax.text(0.5, 0.5, 'Load factors to begin', 
                                ha='center', va='center', transform=self.canvas.ax.transAxes)
            self.canvas.ax.set_xticks([])
            self.canvas.ax.set_yticks([])
            self.canvas.draw()
            return

        num_vars = len(self.factors)
        angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
        angles += angles[:1]  # Close the loop

        self.canvas.ax.set_theta_offset(np.pi / 2)
        self.canvas.ax.set_theta_direction(-1)
        self.canvas.ax.set_thetagrids(np.degrees(angles[:-1]), [f['name'] for f in self.factors])
        
        self.canvas.ax.set_rlabel_position(0)
        self.canvas.ax.set_yticks(range(1, 11, 2))
        self.canvas.ax.set_ylim(0, 10)

        for name, data in self.samples.items():
            values = data['values'] + data['values'][:1] # Close the loop for plotting
            self.canvas.ax.plot(angles, values, color=data['color'], linewidth=2, label=name)
        
        # Only show legend if there are samples
        if self.samples:
            self.canvas.ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))

        self.canvas.draw()

# Matplotlib Canvas Class for embedding in PyQt
class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.ax = self.fig.add_subplot(111, polar=True)
        super().__init__(self.fig)
        self.setParent(parent)

def main():
    # Create example files for user convenience if they don't exist
    try:
        with open("example_factors.json", "x") as f:
            factors_data = [
                {"name": "Factor A", "description": "Description of factor A..."},
                {"name": "Factor B", "description": "Description of factor B..."},
                {"name": "Factor C", "description": "Description of factor C..."},
                {"name": "Factor D", "description": "Description of factor D..."},
                {"name": "Factor E", "description": "Description of factor E..."}
            ]
            json.dump(factors_data, f, indent=2)
    except FileExistsError:
        pass # File already exists, do nothing
    
    app = QApplication(sys.argv)
    ex = SpiderChartApp()
    ex.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()