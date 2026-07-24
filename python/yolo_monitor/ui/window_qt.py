from __future__ import annotations
# Qt monitoring window - optional, tries PySide6
import sys
import time
import cv2
import numpy as np
from typing import List, Optional, Callable

try:
    from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QHBoxLayout, QPushButton, QSlider, QCheckBox
    from PySide6.QtCore import Qt, QTimer, Signal, QObject
    from PySide6.QtGui import QImage, QPixmap
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

if QT_AVAILABLE:
    class QtMonitorWindow(QMainWindow):
        def __init__(self, config, class_names=None):
            super().__init__()
            self.config = config
            self.class_names = class_names or []
            self.setWindowTitle(f"YOLO Monitor - {config.model.path}")
            self.setGeometry(100,100,1280,720)
            central = QWidget()
            self.setCentralWidget(central)
            layout = QVBoxLayout(central)
            self.image_label = QLabel()
            self.image_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(self.image_label)
            self.status_label = QLabel("Starting...")
            layout.addWidget(self.status_label)

            self.conf_slider = QSlider(Qt.Horizontal)
            self.conf_slider.setMinimum(0)
            self.conf_slider.setMaximum(100)
            self.conf_slider.setValue(int(config.conf_thres*100))
            layout.addWidget(self.conf_slider)

            self.latest_frame = None
            self.timer = QTimer()
            self.timer.timeout.connect(self._update_status)

        def update_frame(self, frame: np.ndarray, detections, fps: float, latency: float):
            # convert BGR to RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h,w,ch = rgb.shape
            bytes_per_line = ch*w
            qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pix = QPixmap.fromImage(qimg)
            # scale to label size
            scaled = pix.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(scaled)
            self.latest_frame = frame
            self.status_label.setText(f"FPS: {fps:.1f} Lat: {latency:.1f}ms Dets: {len(detections) if detections else 0}")

        def _update_status(self):
            pass

        def closeEvent(self, event):
            event.accept()
            QApplication.quit()
else:
    class QtMonitorWindow:
        def __init__(self, *args, **kwargs):
            raise ImportError("PySide6 not installed")
