from __future__ import annotations
try:
    from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel, QPushButton, QComboBox, QHBoxLayout, QSlider
    from PySide6.QtCore import Signal, Qt
    QT_AVAILABLE=True
except ImportError:
    QT_AVAILABLE=False

if QT_AVAILABLE:
    class ObjectListPanel(QWidget):
        objectSelected = Signal(str)
        objectDeleted = Signal(str)
        classChanged = Signal(str,int)

        def __init__(self, parent=None):
            super().__init__(parent)
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel("Objects"))
            self.list_widget = QListWidget()
            layout.addWidget(self.list_widget)
            btn_layout = QHBoxLayout()
            self.btn_delete = QPushButton("Delete")
            btn_layout.addWidget(self.btn_delete)
            layout.addLayout(btn_layout)
            self.btn_delete.clicked.connect(self._on_delete)
            self.list_widget.itemClicked.connect(self._on_item_clicked)
            self.class_combo = QComboBox()
            layout.addWidget(QLabel("Class"))
            layout.addWidget(self.class_combo)
            self.class_combo.currentIndexChanged.connect(self._on_class_changed)

        def set_objects(self, objects, class_names):
            self.list_widget.clear()
            self.class_combo.clear()
            self.class_combo.addItems(class_names)
            for obj in objects:
                item = QListWidgetItem(f"{obj.class_name} [{obj.bbox_xyxy[0]:.0f},{obj.bbox_xyxy[1]:.0f},{obj.bbox_xyxy[2]:.0f},{obj.bbox_xyxy[3]:.0f}] {'AI' if obj.is_ai else ''}")
                item.setData(Qt.UserRole, obj.id)
                self.list_widget.addItem(item)

        def _on_item_clicked(self, item):
            oid = item.data(Qt.UserRole)
            self.objectSelected.emit(oid)

        def _on_delete(self):
            cur = self.list_widget.currentItem()
            if cur:
                oid = cur.data(Qt.UserRole)
                self.objectDeleted.emit(oid)

        def _on_class_changed(self, idx):
            cur = self.list_widget.currentItem()
            if cur:
                oid = cur.data(Qt.UserRole)
                self.classChanged.emit(oid, idx)

    class ThumbnailPanel(QWidget):
        imageSelected = Signal(str)
        def __init__(self, parent=None):
            super().__init__(parent)
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel("Images"))
            self.list_widget = QListWidget()
            layout.addWidget(self.list_widget)
            self.list_widget.itemClicked.connect(self._on_click)
        def set_images(self, image_infos):
            self.list_widget.clear()
            for info in image_infos:
                item = QListWidgetItem(f"{info.path.split('/')[-1]} ({len(info.annotations.objects)} objs)")
                item.setData(Qt.UserRole, info.path)
                self.list_widget.addItem(item)
        def _on_click(self, item):
            path = item.data(Qt.UserRole)
            self.imageSelected.emit(path)
else:
    class ObjectListPanel:
        pass
    class ThumbnailPanel:
        pass
