try:
    from .main_window import MainWindow
except ImportError as e:
    MainWindow = None
