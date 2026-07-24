from __future__ import annotations
from typing import List, Dict, Optional
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QComboBox, QCheckBox, QGroupBox, QLineEdit,
    QSpinBox, QDoubleSpinBox, QProgressBar, QTabWidget, QTextEdit,
    QScrollArea, QGridLayout
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor

from ..core.annotation import ImageInfo, AnnotationObject
from ..utils.colors import get_color

class ObjectListPanel(QWidget):
    objectSelected = Signal(str)
    objectDeleted = Signal(str)
    classChanged = Signal(str,int)
    visibilityToggled = Signal(str,bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Objects (Double click to focus)"))

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        self.btn_delete = QPushButton("Delete (Del)")
        self.btn_hide = QPushButton("Hide/Show")
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_hide)
        layout.addLayout(btn_layout)

        layout.addWidget(QLabel("Class for new / selected"))
        self.class_combo = QComboBox()
        layout.addWidget(self.class_combo)

        self.info_label = QLabel("0 objects")
        layout.addWidget(self.info_label)

        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_hide.clicked.connect(self._on_hide)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.itemDoubleClicked.connect(self._on_item_clicked)
        self.class_combo.currentIndexChanged.connect(self._on_class_changed)

    def set_objects(self, objects: List[AnnotationObject], class_names: List[str]):
        self.list_widget.clear()
        self.class_combo.clear()
        self.class_combo.addItems(class_names)
        for obj in objects:
            vis = "👁" if obj.visible else "🚫"
            ai = "🤖" if obj.is_ai else "👤"
            label = f"{vis}{ai} {obj.class_name} [{obj.bbox_xyxy[0]:.0f},{obj.bbox_xyxy[1]:.0f},{obj.bbox_xyxy[2]:.0f},{obj.bbox_xyxy[3]:.0f}] {obj.confidence*100:.0f}%"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, obj.id)
            r,g,b = get_color(obj.class_id)
            item.setBackground(QColor(r,g,b,40))
            if not obj.visible:
                item.setForeground(QColor(100,100,100))
            self.list_widget.addItem(item)
        self.info_label.setText(f"{len(objects)} objects ({sum(1 for o in objects if o.is_ai)} AI)")

    def _on_item_clicked(self, item):
        oid = item.data(Qt.UserRole)
        self.objectSelected.emit(oid)

    def _on_delete(self):
        cur = self.list_widget.currentItem()
        if cur:
            oid = cur.data(Qt.UserRole)
            self.objectDeleted.emit(oid)

    def _on_hide(self):
        cur = self.list_widget.currentItem()
        if cur:
            oid = cur.data(Qt.UserRole)
            # toggle visibility handled in main window, emit with current visible inverted? We'll emit toggle
            self.visibilityToggled.emit(oid, False)

    def _on_class_changed(self, idx):
        cur = self.list_widget.currentItem()
        if cur:
            oid = cur.data(Qt.UserRole)
            self.classChanged.emit(oid, idx)

class ClassManagerPanel(QWidget):
    classAdded = Signal(str)
    classRenamed = Signal(str,str)
    classesFiltered = Signal(list)  # wanted classes list

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Classes"))

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        add_layout = QHBoxLayout()
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("New class name")
        self.btn_add = QPushButton("Add")
        add_layout.addWidget(self.input_name)
        add_layout.addWidget(self.btn_add)
        layout.addLayout(add_layout)

        layout.addWidget(QLabel("Wanted classes (only label these) - empty = all"))
        self.wanted_checks: Dict[str, QCheckBox] = {}
        self.wanted_container = QWidget()
        self.wanted_layout = QVBoxLayout(self.wanted_container)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.wanted_container)
        scroll.setMaximumHeight(150)
        layout.addWidget(scroll)

        btn_filter_layout = QHBoxLayout()
        self.btn_select_all = QPushButton("Select All")
        self.btn_clear_filter = QPushButton("Clear Filter (All)")
        btn_filter_layout.addWidget(self.btn_select_all)
        btn_filter_layout.addWidget(self.btn_clear_filter)
        layout.addLayout(btn_filter_layout)

        self.btn_add.clicked.connect(self._on_add)
        self.btn_select_all.clicked.connect(self._on_select_all)
        self.btn_clear_filter.clicked.connect(self._on_clear_filter)

    def set_classes(self, classes: List[str], wanted: List[str] = None):
        self.list_widget.clear()
        # clear wanted
        for i in reversed(range(self.wanted_layout.count())):
            item = self.wanted_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)

        self.wanted_checks.clear()
        wanted_set = set(wanted or [])

        for idx, cname in enumerate(classes):
            r,g,b = get_color(idx)
            item = QListWidgetItem(f"{idx}: {cname}")
            item.setBackground(QColor(r,g,b,60))
            self.list_widget.addItem(item)

            cb = QCheckBox(cname)
            cb.setChecked(cname in wanted_set if wanted_set else True)
            cb.stateChanged.connect(self._emit_filter)
            self.wanted_layout.addWidget(cb)
            self.wanted_checks[cname] = cb

    def _on_add(self):
        name = self.input_name.text().strip()
        if name:
            self.classAdded.emit(name)
            self.input_name.clear()

    def _on_select_all(self):
        for cb in self.wanted_checks.values():
            cb.setChecked(True)

    def _on_clear_filter(self):
        for cb in self.wanted_checks.values():
            cb.setChecked(True)
        # Actually clear filter means all selected -> empty filter list means all, but we will emit all
        self.classesFiltered.emit([])

    def _emit_filter(self):
        selected = [name for name, cb in self.wanted_checks.items() if cb.isChecked()]
        # if all selected, emit empty = no filter
        if len(selected) == len(self.wanted_checks):
            self.classesFiltered.emit([])
        else:
            self.classesFiltered.emit(selected)

    def get_wanted(self) -> List[str]:
        selected = [name for name, cb in self.wanted_checks.items() if cb.isChecked()]
        if len(selected) == len(self.wanted_checks):
            return []
        return selected

class ThumbnailPanel(QWidget):
    imageSelected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Images"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        top.addWidget(self.search_input)
        layout.addLayout(top)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        self.info_label = QLabel("0 images")
        layout.addWidget(self.info_label)

        self.list_widget.itemClicked.connect(self._on_click)
        self.search_input.textChanged.connect(self._on_search)

        self._all_infos: List[ImageInfo] = []

    def set_images(self, image_infos: List[ImageInfo]):
        self._all_infos = image_infos
        self._refresh("")

    def _refresh(self, filter_text: str):
        self.list_widget.clear()
        ft = filter_text.lower()
        count=0
        for info in self._all_infos:
            name = Path(info.path).name
            if ft and ft not in name.lower() and ft not in info.path.lower():
                continue
            issues = ""
            if info.annotations.llm_analysis:
                qa = info.annotations.llm_analysis.get("qa_score", 1.0)
                if qa < 0.8:
                    issues = f" ⚠️ QA {qa:.2f}"
            item = QListWidgetItem(f"{name} ({len(info.annotations.objects)} objs){issues}")
            item.setData(Qt.UserRole, info.path)
            if info.annotations.status == "needs_fix":
                item.setBackground(QColor(180,60,60,80))
            elif info.annotations.reviewed:
                item.setBackground(QColor(60,180,60,60))
            self.list_widget.addItem(item)
            count+=1
        self.info_label.setText(f"{count}/{len(self._all_infos)} images")

    def _on_click(self, item):
        path = item.data(Qt.UserRole)
        self.imageSelected.emit(path)

    def _on_search(self, text):
        self._refresh(text)

class BatchPanel(QWidget):
    batchRequested = Signal(dict)  # config dict
    stopRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Batch Processing - Only Wanted Classes"))

        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Input folder path")
        layout.addWidget(self.folder_input)

        self.btn_browse = QPushButton("Browse Folder")
        layout.addWidget(self.btn_browse)

        conf_layout = QHBoxLayout()
        conf_layout.addWidget(QLabel("Conf:"))
        self.conf_spin = QDoubleSpinBox()
        self.conf_spin.setRange(0.05, 0.95)
        self.conf_spin.setValue(0.35)
        self.conf_spin.setSingleStep(0.05)
        conf_layout.addWidget(self.conf_spin)
        conf_layout.addWidget(QLabel("IoU:"))
        self.iou_spin = QDoubleSpinBox()
        self.iou_spin.setRange(0.1, 0.95)
        self.iou_spin.setValue(0.45)
        conf_layout.addWidget(self.iou_spin)
        layout.addLayout(conf_layout)

        self.recursive_check = QCheckBox("Recursive")
        self.recursive_check.setChecked(True)
        layout.addWidget(self.recursive_check)

        self.overwrite_check = QCheckBox("Overwrite AI boxes")
        self.overwrite_check.setChecked(True)
        layout.addWidget(self.overwrite_check)

        self.keep_human_check = QCheckBox("Keep human boxes")
        self.keep_human_check.setChecked(True)
        layout.addWidget(self.keep_human_check)

        self.wanted_label = QLabel("Wanted classes from Class Manager panel will be used")
        self.wanted_label.setWordWrap(True)
        layout.addWidget(self.wanted_label)

        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("▶ Start Batch")
        self.btn_stop = QPushButton("⏹ Stop")
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        layout.addLayout(btn_layout)

        self.progress = QProgressBar()
        layout.addWidget(self.progress)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120)
        layout.addWidget(self.log_text)

        self.btn_start.clicked.connect(self._on_start)
        self.btn_stop.clicked.connect(lambda: self.stopRequested.emit())

    def set_folder(self, folder: str):
        self.folder_input.setText(folder)

    def set_wanted_info(self, wanted: List[str]):
        if not wanted:
            self.wanted_label.setText("Wanted: ALL classes")
        else:
            self.wanted_label.setText(f"Wanted: {', '.join(wanted)}")

    def _on_start(self):
        folder = self.folder_input.text().strip()
        if not folder:
            self.log_text.append("❌ No folder selected")
            return
        config = {
            "input_folder": folder,
            "recursive": self.recursive_check.isChecked(),
            "conf": self.conf_spin.value(),
            "iou": self.iou_spin.value(),
            "overwrite_ai": self.overwrite_check.isChecked(),
            "keep_human": self.keep_human_check.isChecked(),
        }
        self.batchRequested.emit(config)
        self.log_text.append(f"Started batch for {folder}")

    def update_progress(self, current, total, path):
        self.progress.setMaximum(total)
        self.progress.setValue(current)
        if current % 10 == 0:
            self.log_text.append(f"[{current}/{total}] {Path(path).name}")

    def batch_done(self, result):
        self.log_text.append(f"✅ Done: {result.processed}/{result.total_images} in {result.elapsed_sec:.1f}s, errors {result.errors}")

class LLMPanel(QWidget):
    analyzeCurrentRequested = Signal()
    analyzeDatasetRequested = Signal()
    queryRequested = Signal(str)
    modelLoadRequested = Signal(str, str)  # path, backend

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("LLM - Offline Label QA & Management"))

        model_layout = QHBoxLayout()
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("models/llm/tinyllama-1.1b-chat.gguf or HF folder")
        model_layout.addWidget(self.model_input)
        self.btn_browse_model = QPushButton("Browse")
        model_layout.addWidget(self.btn_browse_model)
        layout.addLayout(model_layout)

        backend_layout = QHBoxLayout()
        backend_layout.addWidget(QLabel("Backend:"))
        self.backend_combo = QComboBox()
        self.backend_combo.addItems(["auto","llama_cpp","transformers","onnx","dummy"])
        backend_layout.addWidget(self.backend_combo)
        self.btn_load = QPushButton("Load LLM")
        backend_layout.addWidget(self.btn_load)
        layout.addLayout(backend_layout)

        self.status_label = QLabel("Backend: dummy (heuristic)")
        layout.addWidget(self.status_label)

        btns = QHBoxLayout()
        self.btn_analyze_current = QPushButton("Analyze Current Image")
        self.btn_analyze_dataset = QPushButton("Analyze Dataset")
        btns.addWidget(self.btn_analyze_current)
        btns.addWidget(self.btn_analyze_dataset)
        layout.addLayout(btns)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("LLM analysis results will appear here...")
        layout.addWidget(self.result_text)

        query_layout = QHBoxLayout()
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Ask: images with more than 3 cars, or به فارسی بپرس")
        self.btn_query = QPushButton("Ask LLM")
        query_layout.addWidget(self.query_input)
        query_layout.addWidget(self.btn_query)
        layout.addLayout(query_layout)

        self.btn_analyze_current.clicked.connect(lambda: self.analyzeCurrentRequested.emit())
        self.btn_analyze_dataset.clicked.connect(lambda: self.analyzeDatasetRequested.emit())
        self.btn_query.clicked.connect(self._on_query)
        self.btn_load.clicked.connect(self._on_load)
        self.query_input.returnPressed.connect(self._on_query)

    def _on_query(self):
        q = self.query_input.text().strip()
        if q:
            self.queryRequested.emit(q)

    def _on_load(self):
        path = self.model_input.text().strip()
        backend = self.backend_combo.currentText()
        self.modelLoadRequested.emit(path, backend)

    def set_status(self, text: str):
        self.status_label.setText(text)

    def set_result(self, text: str):
        self.result_text.setPlainText(text)

    def append_result(self, text: str):
        self.result_text.append(text)

    def set_model_path(self, path: str):
        self.model_input.setText(path)
