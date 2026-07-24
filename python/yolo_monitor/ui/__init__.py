from .window_opencv import OpenCVMonitorWindow
try:
    from .window_qt import QtMonitorWindow
except Exception:
    QtMonitorWindow = None
