from __future__ import annotations
import sys
from pathlib import Path
import cv2

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QFileDialog, QSplitter, QStatusBar, QToolBar, QMessageBox, QApplication,
    QTabWidget, QGroupBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction

from .canvas import AnnotationCanvas
from .panels import ObjectListPanel, ThumbnailPanel, ClassManagerPanel, BatchPanel, LLMPanel
from .styles import DARK_STYLE
from ..core.project import AnnotationProject
from ..core.annotation import AnnotationObject
from ..core.dataset import DatasetManager
from ..ai.detector import YOLODetector
from ..ai.sam import SAMHelper
from ..ai.llm_analyzer import LLMAnalyzer
from ..ai.batch_processor import BatchProcessor, BatchConfig
from ..exporters import YOLOExporter, COCOExporter, VOCExporter
from ..utils.colors import generate_colors
from loguru import logger

class MainWindow(QMainWindow):
    def __init__(self, project_path: str = None, model_path: str = None, llm_model_path: str = None, offline: bool = True, wanted_classes: str = None):
        super().__init__()
        self.setWindowTitle("Offline Pro Annotator 2.0 - Professional AI + LLM")
        self.setGeometry(100,100,1800,950)

        self.project: AnnotationProject | None = None
        self.model_path = model_path
        self.llm_model_path = llm_model_path
        self.offline = offline
        self.current_image_path: str | None = None
        self.current_cv_image = None
        self.detector: YOLODetector | None = None
        self.sam_helper: SAMHelper | None = None
        self.llm_analyzer: LLMAnalyzer | None = None
        self.batch_processor: BatchProcessor | None = None
        self.dataset_manager: DatasetManager | None = None
        self.class_names = ["person","car","bicycle","dog","cat","truck","bus","motorcycle"]

        # UI setup
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        splitter = QSplitter(Qt.Horizontal)

        # left tabs: thumbnails, classes, batch, llm
        left_tabs = QTabWidget()
        self.thumb_panel = ThumbnailPanel()
        self.class_panel = ClassManagerPanel()
        self.batch_panel = BatchPanel()
        self.llm_panel = LLMPanel()

        left_tabs.addTab(self.thumb_panel, "Images")
        left_tabs.addTab(self.class_panel, "Classes")
        left_tabs.addTab(self.batch_panel, "Batch")
        left_tabs.addTab(self.llm_panel, "LLM QA")
        splitter.addWidget(left_tabs)

        # center: canvas
        self.canvas = AnnotationCanvas()
        splitter.addWidget(self.canvas)

        # right: object list + stats
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        self.obj_panel = ObjectListPanel()
        right_layout.addWidget(self.obj_panel)

        # stats label
        self.stats_label = QLabel("Stats: 0 images, 0 objects")
        right_layout.addWidget(self.stats_label)

        splitter.addWidget(right_widget)

        splitter.setSizes([350, 900, 350])
        main_layout.addWidget(splitter)

        # status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Offline Pro Annotator - آفلاین - Ready")

        # toolbar
        toolbar = QToolBar("Main")
        self.addToolBar(toolbar)
        act_open = QAction("📁 Open Project", self); act_open.triggered.connect(self.open_project_dialog); toolbar.addAction(act_open)
        act_import = QAction("🖼 Import Images", self); act_import.triggered.connect(self.import_images_dialog); toolbar.addAction(act_import)
        act_import_video = QAction("🎬 Import Video", self); act_import_video.triggered.connect(self.import_video_dialog); toolbar.addAction(act_import_video)
        act_import_folder_batch = QAction("📂 Batch Folder", self); act_import_folder_batch.triggered.connect(self.select_batch_folder); toolbar.addAction(act_import_folder_batch)
        act_auto = QAction("🤖 Auto-Label Current", self); act_auto.triggered.connect(self.auto_label_current); toolbar.addAction(act_auto)
        act_auto_all = QAction("🤖 Auto-Label All", self); act_auto_all.triggered.connect(self.auto_label_all); toolbar.addAction(act_auto_all)
        act_export_yolo = QAction("Export YOLO", self); act_export_yolo.triggered.connect(self.export_yolo); toolbar.addAction(act_export_yolo)
        act_export_coco = QAction("Export COCO", self); act_export_coco.triggered.connect(self.export_coco); toolbar.addAction(act_export_coco)
        act_export_voc = QAction("Export VOC", self); act_export_voc.triggered.connect(self.export_voc); toolbar.addAction(act_export_voc)
        act_save = QAction("💾 Save Project", self); act_save.triggered.connect(self.save_project); toolbar.addAction(act_save)
        act_llm_qa = QAction("🧠 LLM QA Current", self); act_llm_qa.triggered.connect(self.llm_analyze_current); toolbar.addAction(act_llm_qa)

        # connections
        self.thumb_panel.imageSelected.connect(self.load_image)
        self.obj_panel.objectSelected.connect(self.select_object)
        self.obj_panel.objectDeleted.connect(self.delete_object)
        self.obj_panel.classChanged.connect(self.change_object_class)
        self.obj_panel.visibilityToggled.connect(self.toggle_visibility)
        self.canvas.objectCreated.connect(self.on_object_created)
        self.canvas.objectModified.connect(self.on_object_modified)
        self.canvas.selectionChanged.connect(self.on_canvas_selection)
        self.canvas.objectDeleted.connect(self.delete_object)

        self.class_panel.classAdded.connect(self.add_class)
        self.class_panel.classesFiltered.connect(self.on_wanted_classes_changed)

        self.batch_panel.batchRequested.connect(self.start_batch)
        self.batch_panel.stopRequested.connect(self.stop_batch)

        self.llm_panel.analyzeCurrentRequested.connect(self.llm_analyze_current)
        self.llm_panel.analyzeDatasetRequested.connect(self.llm_analyze_dataset)
        self.llm_panel.queryRequested.connect(self.llm_query)
        self.llm_panel.modelLoadRequested.connect(self.llm_load_model)

        # Load project if provided
        if project_path:
            self.open_project(project_path)
        else:
            self.project = AnnotationProject.create("datasets/default_project", classes=self.class_names)
            self.refresh_all()

        if wanted_classes:
            self.project.set_wanted_classes(wanted_classes)
            self.class_panel.set_classes(self.project.classes, self.project.wanted_classes)

        # Load models
        if model_path and Path(model_path).exists():
            self.load_detector(model_path)
        else:
            # try default
            default_model = Path("models/yolov8n.onnx")
            if default_model.exists():
                self.load_detector(str(default_model))

        # LLM
        if llm_model_path and Path(llm_model_path).exists():
            self.llm_load_model(llm_model_path, "auto")
            self.llm_panel.set_model_path(llm_model_path)
        else:
            # dummy backend always works
            self.llm_analyzer = LLMAnalyzer(model_path=None, backend="dummy")
            self.llm_analyzer.load()
            self.llm_panel.set_status(f"Backend: {self.llm_analyzer.backend_used.value} - Heuristic (no LLM model). Load GGUF for AI.")

        self.dataset_manager = DatasetManager(self.project.classes if self.project else self.class_names)

    def load_detector(self, model_path: str):
        try:
            wanted = list(self.project.wanted_classes) if self.project and self.project.wanted_classes else []
            self.detector = YOLODetector(model_path=model_path, device="auto", conf_thres=0.35, wanted_classes=wanted)
            self.detector.load()
            self.detector.warmup(3)
            self.statusBar.showMessage(f"✅ YOLO loaded: {model_path} - Classes: {self.detector.class_names[:5]}...")
            self.batch_processor = BatchProcessor(self.project, self.detector)
        except Exception as e:
            self.statusBar.showMessage(f"❌ YOLO load failed: {e}")
            QMessageBox.warning(self, "Model load failed", f"{e}")

    def open_project_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Open Project Folder")
        if folder:
            self.open_project(folder)

    def open_project(self, path: str):
        try:
            if Path(path).exists() and (Path(path)/"project.yaml").exists():
                self.project = AnnotationProject.open(path)
            else:
                self.project = AnnotationProject.create(path, classes=self.class_names)
                # try import images if folder has images
                self.project.import_images(path)
            self.class_names = self.project.classes
            self.dataset_manager = DatasetManager(self.project.classes)
            self.refresh_all()
            self.statusBar.showMessage(f"Project opened: {path} - {len(self.project.images)} images - Wanted: {self.project.wanted_classes or 'ALL'}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open project: {e}")

    def refresh_all(self):
        if not self.project:
            return
        self.thumb_panel.set_images(self.project.get_image_list())
        self.class_panel.set_classes(self.project.classes, list(self.project.wanted_classes))
        self.batch_panel.set_wanted_info(list(self.project.wanted_classes))
        self.update_stats()

    def refresh_thumbnails(self):
        if not self.project:
            return
        self.thumb_panel.set_images(self.project.get_image_list())

    def update_stats(self):
        if not self.project:
            return
        mgr = DatasetManager(self.project.classes)
        stats = mgr.compute_stats(self.project.get_image_list())
        self.stats_label.setText(f"Images: {stats['total_images']} | Objects: {stats['total_objects']} | Reviewed: {stats['reviewed']}\nClasses: {stats['class_distribution']}")

    def load_image(self, path: str):
        self.current_image_path = path
        img = cv2.imread(path)
        if img is None:
            self.statusBar.showMessage(f"Failed to load {path}")
            return
        self.current_cv_image = img
        info = self.project.images.get(path)
        objs = info.annotations.objects if info else []
        self.canvas.set_image(img, objs, self.project.classes if self.project else self.class_names)
        self.obj_panel.set_objects(objs, self.project.classes if self.project else self.class_names)
        self.statusBar.showMessage(f"Loaded {Path(path).name} - {img.shape[1]}x{img.shape[0]} - {len(objs)} objs - Drag: create, Ctrl+Drag: pan, Wheel: zoom, Del: delete")

    def select_object(self, oid: str):
        self.canvas.selected_id = oid
        self.canvas.update()

    def delete_object(self, oid: str):
        if not self.project or not self.current_image_path:
            return
        info = self.project.images.get(self.current_image_path)
        if not info:
            return
        info.annotations.objects = [o for o in info.annotations.objects if o.id!=oid]
        self.canvas.set_image(self.current_cv_image, info.annotations.objects, self.project.classes)
        self.obj_panel.set_objects(info.annotations.objects, self.project.classes)
        self.canvas.update()
        self.update_stats()

    def toggle_visibility(self, oid: str, visible: bool = None):
        if not self.project or not self.current_image_path:
            return
        info = self.project.images.get(self.current_image_path)
        if not info:
            return
        for obj in info.annotations.objects:
            if obj.id==oid:
                obj.visible = not obj.visible
                break
        self.canvas.set_image(self.current_cv_image, info.annotations.objects, self.project.classes)
        self.obj_panel.set_objects(info.annotations.objects, self.project.classes)
        self.canvas.update()

    def change_object_class(self, oid: str, class_idx: int):
        if not self.project or not self.current_image_path:
            return
        info = self.project.images.get(self.current_image_path)
        if not info:
            return
        for obj in info.annotations.objects:
            if obj.id==oid:
                obj.class_id = class_idx
                obj.class_name = self.project.classes[class_idx] if class_idx < len(self.project.classes) else str(class_idx)
                break
        self.canvas.update()
        self.obj_panel.set_objects(info.annotations.objects, self.project.classes)

    def on_object_created(self, obj: AnnotationObject):
        if not self.project or not self.current_image_path:
            return
        info = self.project.images.get(self.current_image_path)
        if not info:
            return
        combo_idx = self.obj_panel.class_combo.currentIndex() if hasattr(self.obj_panel, 'class_combo') else 0
        if combo_idx>=0 and combo_idx < len(self.project.classes):
            obj.class_id = combo_idx
            obj.class_name = self.project.classes[combo_idx]
        # check wanted filter - if new object class not wanted, warn but still add?
        if self.project.wanted_classes and obj.class_name not in self.project.wanted_classes:
            # optionally still add but highlight
            pass
        info.annotations.objects.append(obj)
        self.canvas.set_image(self.current_cv_image, info.annotations.objects, self.project.classes)
        self.obj_panel.set_objects(info.annotations.objects, self.project.classes)
        self.update_stats()

    def on_object_modified(self, obj):
        if not self.project or not self.current_image_path:
            return
        self.obj_panel.set_objects(self.project.images[self.current_image_path].annotations.objects, self.project.classes)
        self.update_stats()

    def on_canvas_selection(self, obj):
        self.obj_panel.list_widget.clearSelection()
        for i in range(self.obj_panel.list_widget.count()):
            item = self.obj_panel.list_widget.item(i)
            if item.data(Qt.UserRole)==obj.id:
                self.obj_panel.list_widget.setCurrentItem(item)
                break

    def add_class(self, name: str):
        if self.project:
            self.project.add_class(name)
            self.refresh_all()

    def on_wanted_classes_changed(self, wanted: List[str]):
        if self.project:
            self.project.set_wanted_classes(wanted)
            if self.detector:
                self.detector.set_wanted_classes(wanted)
            self.batch_panel.set_wanted_info(wanted)
            self.statusBar.showMessage(f"Wanted classes set to: {wanted or 'ALL'}")

    def import_images_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Import Images Folder")
        if folder and self.project:
            count = self.project.import_images(folder, copy=False, recursive=True)
            self.refresh_all()
            self.statusBar.showMessage(f"Imported {count} images from {folder}")

    def import_video_dialog(self):
        file, _ = QFileDialog.getOpenFileName(self, "Import Video", "", "Videos (*.mp4 *.avi *.mkv *.mov)")
        if file and self.project:
            try:
                count = self.project.import_video(file, fps=1.0)
                self.refresh_all()
                self.statusBar.showMessage(f"Extracted {count} frames from {file}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Video import failed: {e}")

    def select_batch_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Batch Folder - هزاران عکس")
        if folder:
            self.batch_panel.set_folder(folder)

    def start_batch(self, config: dict):
        if not self.project or not self.detector:
            QMessageBox.warning(self, "No Model", "Load YOLO model first")
            return
        wanted = self.class_panel.get_wanted()
        batch_cfg = BatchConfig(
            input_folder=config["input_folder"],
            recursive=config["recursive"],
            wanted_classes=wanted,
            conf_thres=config["conf"],
            iou_thres=config["iou"],
            overwrite_ai=config["overwrite_ai"],
            keep_human=config["keep_human"],
            save_after=50
        )
        # update detector conf
        self.detector.conf_thres = config["conf"]
        self.detector.iou_thres = config["iou"]

        def progress_cb(cur, total, path):
            self.batch_panel.update_progress(cur, total, path)
            self.statusBar.showMessage(f"Batch {cur}/{total}: {Path(path).name}")

        def done_cb(result):
            self.batch_panel.batch_done(result)
            self.refresh_all()
            self.statusBar.showMessage(f"Batch done: {result.processed}/{result.total_images}")

        self.batch_processor.process_async(batch_cfg, progress_cb=progress_cb, done_cb=done_cb)

    def stop_batch(self):
        if self.batch_processor:
            self.batch_processor.stop()
            self.statusBar.showMessage("Batch stopping...")

    def auto_label_current(self):
        if not self.project or not self.current_image_path:
            return
        if not self.detector:
            QMessageBox.warning(self, "No Model", "Load YOLO model")
            return
        try:
            info = self.project.images.get(self.current_image_path)
            if not info:
                return
            dets = self.detector.detect_path(self.current_image_path)
            # filter by wanted
            wanted = self.class_panel.get_wanted()
            if wanted:
                dets = [d for d in dets if d.class_name in wanted]
            # keep human if desired? For current, replace AI only
            existing_human = [o for o in info.annotations.objects if not o.is_ai]
            info.annotations.objects = existing_human + dets
            self.canvas.set_image(self.current_cv_image, info.annotations.objects, self.project.classes)
            self.obj_panel.set_objects(info.annotations.objects, self.project.classes)
            self.statusBar.showMessage(f"Auto-labeled current: {len(dets)} detections (wanted: {wanted or 'ALL'})")
            self.update_stats()
        except Exception as e:
            QMessageBox.warning(self, "Auto-label failed", f"{e}")

    def auto_label_all(self):
        if not self.project:
            return
        if not self.detector:
            QMessageBox.warning(self, "No Model", "Load YOLO model")
            return
        wanted = self.class_panel.get_wanted()
        self.detector.set_wanted_classes(wanted)
        count=0
        for img_info in self.project.get_image_list():
            try:
                dets = self.detector.detect_path(img_info.path)
                if wanted:
                    dets = [d for d in dets if d.class_name in wanted]
                existing_human = [o for o in img_info.annotations.objects if not o.is_ai]
                img_info.annotations.objects = existing_human + dets
                count+=1
            except Exception as e:
                print(f"Auto-label failed {img_info.path}: {e}")
        if self.current_image_path:
            self.load_image(self.current_image_path)
        self.refresh_thumbnails()
        self.update_stats()
        self.statusBar.showMessage(f"Auto-labeled {count} images - Wanted: {wanted or 'ALL'}")

    def llm_load_model(self, path: str, backend: str):
        if not path:
            QMessageBox.warning(self, "LLM", "Select LLM model path first")
            return
        try:
            self.llm_analyzer = LLMAnalyzer(model_path=path, backend=backend, device="cpu")
            self.llm_analyzer.load()
            self.llm_panel.set_status(f"✅ Loaded {backend}: {Path(path).name} - Backend used: {self.llm_analyzer.backend_used.value}")
            self.statusBar.showMessage(f"LLM loaded: {path} backend {self.llm_analyzer.backend_used.value}")
        except Exception as e:
            QMessageBox.warning(self, "LLM Load Failed", f"{e}\nFalling back to DUMMY heuristic")
            self.llm_analyzer = LLMAnalyzer(model_path=None, backend="dummy")
            self.llm_analyzer.load()

    def llm_analyze_current(self):
        if not self.project or not self.current_image_path:
            QMessageBox.warning(self, "LLM", "No image selected")
            return
        if not self.llm_analyzer:
            self.llm_analyzer = LLMAnalyzer(model_path=None, backend="dummy")
            self.llm_analyzer.load()
        info = self.project.images.get(self.current_image_path)
        if not info:
            return
        result = self.llm_analyzer.analyze_image_labels(info.annotations, self.project.classes)
        text = f"Image: {Path(self.current_image_path).name}\nQA Score: {result.qa_score:.2f}\nDescription: {result.description}\n\nIssues ({len(result.issues)}):\n"
        for iss in result.issues[:10]:
            text += f"- [{iss.severity}] {iss.type}: {iss.message}\n"
        text += f"\nSuggestions ({len(result.suggestions)}):\n"
        for sug in result.suggestions[:10]:
            text += f"- {sug.type}: {sug.message}\n"
        text += f"\n--- LLM Raw ---\n{result.llm_raw[:1000]}"
        self.llm_panel.set_result(text)
        self.statusBar.showMessage(f"LLM analyzed current - QA {result.qa_score:.2f} - {len(result.issues)} issues")

    def llm_analyze_dataset(self):
        if not self.project:
            return
        if not self.llm_analyzer:
            self.llm_analyzer = LLMAnalyzer(model_path=None, backend="dummy")
            self.llm_analyzer.load()
        report = self.llm_analyzer.analyze_dataset(self.project.get_image_list(), self.project.classes)
        text = f"Dataset: {report.total_images} images, {report.total_objects} objects\n"
        text += f"Distribution: {report.class_distribution}\n"
        text += f"Issues summary: {report.issues_summary}\n"
        text += f"\nDescription: {report.description}\n\nSuggestions:\n"
        for sug in report.suggestions:
            text += f"- {sug.type}: {sug.message}\n"
        text += f"\n--- Stats ---\n{report.stats}\n\n--- LLM Raw ---\n{report.llm_raw[:2000]}"
        self.llm_panel.set_result(text)
        self.statusBar.showMessage(f"Dataset analyzed - {report.total_images} images")

    def llm_query(self, question: str):
        if not self.project:
            return
        if not self.llm_analyzer:
            self.llm_analyzer = LLMAnalyzer(model_path=None, backend="dummy")
            self.llm_analyzer.load()
        answer = self.llm_analyzer.query_dataset(question, self.project.get_image_list())
        self.llm_panel.append_result(f"\n\nQ: {question}\nA: {answer}")

    def export_yolo(self):
        if not self.project:
            return
        out = QFileDialog.getExistingDirectory(self, "Export YOLO to folder")
        if out:
            # remove unwanted objects before export if filtered?
            images = self.project.get_image_list()
            # if wanted filter active, export only wanted?
            wanted = self.class_panel.get_wanted()
            if wanted:
                # filter objects for export
                from ..core.dataset import DatasetManager
                mgr = DatasetManager(self.project.classes)
                images = mgr.filter_by_wanted_classes(images, wanted)
            exporter = YOLOExporter(self.project.project_path, self.project.classes)
            exporter.export(images, output_dir=out)
            QMessageBox.information(self, "Export", f"YOLO exported to {out}")

    def export_coco(self):
        if not self.project:
            return
        file, _ = QFileDialog.getSaveFileName(self, "Export COCO JSON", "coco.json", "JSON (*.json)")
        if file:
            exporter = COCOExporter(self.project.classes)
            exporter.export(self.project.get_image_list(), file)
            QMessageBox.information(self, "Export", f"COCO exported to {file}")

    def export_voc(self):
        if not self.project:
            return
        out = QFileDialog.getExistingDirectory(self, "Export VOC to folder")
        if out:
            exporter = VOCExporter(self.project.classes)
            exporter.export(self.project.get_image_list(), out)
            QMessageBox.information(self, "Export", f"VOC exported to {out}")

    def save_project(self):
        if self.project:
            self.project.save()
            self.statusBar.showMessage("Project saved")
