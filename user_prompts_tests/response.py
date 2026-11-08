import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton, QTableWidget, QTableWidgetItem
import matplotlib.pyplot as plt
import psutil
import time

class TaskManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Task Manager")
        self.setGeometry(100, 100, 800, 600)

        # Create a layout
        layout = QVBoxLayout()

        # Create a table to display CPU, GPU, RAM stats
        self.stats_table = QTableWidget(3, 2)
        self.stats_table.setHorizontalHeaderLabels(["Stat", "Value"])
        layout.addWidget(self.stats_table)

        # Create a button to update stats
        self.update_stats_button = QPushButton("Update Stats")
        self.update_stats_button.clicked.connect(self.update_stats)
        layout.addWidget(self.update_stats_button)

        # Create a widget to display live usage
        self.live_usage_widget = QWidget()
        self.live_usage_layout = QVBoxLayout(self.live_usage_widget)
        self.live_usage_layout.addWidget(QLabel("Live Usage:"))
        self.live_usage_label = QLabel("0%")
        self.live_usage_layout.addWidget(self.live_usage_label)
        layout.addWidget(self.live_usage_widget)

        # Create a figure and axis for the graphs
        self.fig, self.ax = plt.subplots()
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Value")
        self.ax.set_title("Live Stats")
        self.ax.grid(True)

        # Create a canvas to display the graph
        self.canvas = matplotlib.backends.backend_qt5agg.FigureCanvasQTAgg(self.fig)
        layout.addWidget(self.canvas)

        # Set the layout
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Start the timer to update stats
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(1000)  # Update every second

    def update_stats(self):
        # Get CPU stats
        cpu_stats = psutil.cpu_percent(interval=1)
        self.stats_table.setItem(0, 0, QTableWidgetItem("CPU"))
        self.stats_table.setItem(0, 1, QTableWidgetItem(f"{cpu_stats}%"))

        # Get GPU stats
        gpu_stats = psutil.cpu_percent(interval=1)
        self.stats_table.setItem(1, 0, QTableWidgetItem("GPU"))
        self.stats_table.setItem(1, 1, QTableWidgetItem(f"{gpu_stats}%"))

        # Get RAM stats
        ram_stats = psutil.virtual_memory().percent
        self.stats_table.setItem(2, 0, QTableWidgetItem("RAM"))
        self.stats_table.setItem(2, 1, QTableWidgetItem(f"{ram_stats}%"))

        # Get live usage
        live_usage = "0%"
        self.live_usage_label.setText(live_usage)

        # Update the graph
        self.ax.clear()
        self.ax.plot(time.time(), cpu_stats, label="CPU")
        self.ax.plot(time.time(), gpu_stats, label="GPU")
        self.ax.plot(time.time(), ram_stats, label="RAM")
        self.ax.plot(time.time(), float(live_usage), label="Live Usage")
        self.ax.legend()
        self.canvas.draw()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TaskManagerWindow()
    window.show()
    sys.exit(app.exec_())