#
# This program is largely based on the TelemFFB distribution (https://github.com/walmis/TelemFFB).
#

from PyQt6.QtWidgets import QWidget, QVBoxLayout
import pyqtgraph as pg

class FourQuadrantPlot(QWidget):
    """
    A custom widget that displays a four-quadrant plot with a single data point
    and a text overlay for the current coordinates.
    """
    def __init__(self, title, x_label="X-Axis", y_label="Y-Axis", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        
        # Create a plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setTitle(title)
        self.plot_widget.setLabel('left', y_label)
        self.plot_widget.setLabel('bottom', x_label)
        
        # Set axis limits and add grid lines
        self.plot_widget.setXRange(-1.1, 1.1)
        self.plot_widget.setYRange(-1.1, 1.1)
        self.plot_widget.showGrid(x=True, y=True, alpha=0.5)
        self.plot_widget.getPlotItem().hideAxis('bottom')
        self.plot_widget.getPlotItem().hideAxis('left')

        # Add zero-lines
        self.plot_widget.addLine(x=0, pen=pg.mkPen('gray', width=1))
        self.plot_widget.addLine(y=0, pen=pg.mkPen('gray', width=1))

        # Create a scatter plot item for our single data point
        self.scatter = pg.ScatterPlotItem(
            size=15, 
            pen=pg.mkPen(None), 
            brush=pg.mkBrush(255, 0, 0, 200)
        )
        self.plot_widget.addItem(self.scatter)

        # Add a text item for displaying coordinates
        self.text_item = pg.TextItem(anchor=(1, 0)) # Anchor to top-right
        self.plot_widget.addItem(self.text_item)
        self.text_item.setPos(1.05, 1.05) # Position slightly outside the plot range

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.plot_widget)
        self.setLayout(layout)

    def update_point(self, x, y):
        """Updates the position of the data point and the text overlay on the plot."""
        self.scatter.setData([x], [y])
        self.text_item.setText(f"X: {x:.3f}\nY: {y:.3f}")

if __name__ == '__main__':
    import sys
    import random
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from PyQt6.QtCore import QTimer

    class TestWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.plot = FourQuadrantPlot("Test Plot")
            self.setCentralWidget(self.plot)
            
            self.timer = QTimer()
            self.timer.setInterval(50) # Update every 50ms
            self.timer.timeout.connect(self.update_data)
            self.timer.start()

        def update_data(self):
            x = random.uniform(-1, 1)
            y = random.uniform(-1, 1)
            self.plot.update_point(x, y)

    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec()) 