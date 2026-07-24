DARK_STYLE = """
QWidget {
    background-color: #1e1e1e;
    color: #e0e0e0;
    font-family: 'Segoe UI', Arial;
    font-size: 13px;
}
QMainWindow {
    background-color: #1e1e1e;
}
QToolBar {
    background-color: #2a2a2a;
    border: none;
    padding: 4px;
    spacing: 4px;
}
QToolBar QToolButton {
    background-color: #3a3a3a;
    border: 1px solid #4a4a4a;
    border-radius: 4px;
    padding: 6px 12px;
}
QToolBar QToolButton:hover {
    background-color: #4a4a4a;
    border: 1px solid #5a5a5a;
}
QPushButton {
    background-color: #3a3a3a;
    border: 1px solid #555;
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton:hover {
    background-color: #4a4a4a;
}
QPushButton:pressed {
    background-color: #2a2a2a;
}
QListWidget {
    background-color: #252525;
    border: 1px solid #3a3a3a;
    border-radius: 6px;
    padding: 2px;
}
QListWidget::item {
    padding: 6px;
    border-radius: 4px;
}
QListWidget::item:selected {
    background-color: #3a5a8a;
}
QListWidget::item:hover {
    background-color: #2a3a4a;
}
QLabel {
    color: #e0e0e0;
}
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
    background-color: #2a2a2a;
    border: 1px solid #4a4a4a;
    border-radius: 4px;
    padding: 4px 8px;
}
QProgressBar {
    background-color: #2a2a2a;
    border: 1px solid #4a4a4a;
    border-radius: 4px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #4a8a3a;
    border-radius: 3px;
}
QTabWidget::pane {
    border: 1px solid #3a3a3a;
    background: #1e1e1e;
}
QTabBar::tab {
    background: #2a2a2a;
    border: 1px solid #3a3a3a;
    padding: 6px 12px;
}
QTabBar::tab:selected {
    background: #3a3a3a;
}
"""
