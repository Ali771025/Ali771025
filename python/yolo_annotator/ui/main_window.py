from __future__ import annotations
import sys
from pathlib import Path
import cv2
import yaml

try:
    from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFileDialog, QSplitter, QStatusBar, QToolBar, QMessageBox, QApplication
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QAction
    QT_AVAILABLE=True
except ImportError:
    QT_AVAILABLE=False

if QT_AVAILABLE:
    from .canvas import AnnotationCanvas
    from .panels import ObjectListPanel, ThumbnailPanel
    from ..core.project import AnnotationProject
    from ..core.annotation import AnnotationObject
    from ..ai.auto_labeler import AutoLabeler
    from ..exporters import YOLOExporter, COCOExporter, VOCExporter
    from ..utils.colors import generate_colors

    class MainWindow(QMainWindow):
        def __init__(self, project_path: str = None, model_path: str = None, offline: bool = True):
            super().__init__()
            self.setWindowTitle("Offline YOLO Annotator - Professional")
            self.setGeometry(100,100,1600,900)
            self.project: AnnotationProject | None = None
            self.model_path = model_path
            self.offline = offline
            self.current_image_path: str | None = None
            self.current_cv_image = None
            self.auto_labeler: AutoLabeler | None = None
            self.class_names = ["person","car","bicycle","dog","cat"]

            # UI setup
            central = QWidget()
            self.setCentralWidget(central)
            main_layout = QHBoxLayout(central)

            splitter = QSplitter(Qt.Horizontal)

            # left: thumbnails
            self.thumb_panel = ThumbnailPanel()
            splitter.addWidget(self.thumb_panel)

            # center: canvas
            self.canvas = AnnotationCanvas()
            splitter.addWidget(self.canvas)

            # right: object list
            self.obj_panel = ObjectListPanel()
            splitter.addWidget(self.obj_panel)

            splitter.setSizes([300,900,300])
            main_layout.addWidget(splitter)

            # status bar
            self.statusBar = QStatusBar()
            self.setStatusBar(self.statusBar)
            self.statusBar.showMessage("Offline mode" if offline else "Online mode")

            # toolbar
            toolbar = QToolBar("Main")
            self.addToolBar(toolbar)
            act_open = QAction("Open Project", self)
            act_open.triggered.connect(self.open_project_dialog)
            toolbar.addAction(act_open)
            act_import = QAction("Import Images", self)
            act_import.triggered.connect(self.import_images_dialog)
            toolbar.addAction(act_import)
            act_import_video = QAction("Import Video", self)
            act_import_video.triggered.connect(self.import_video_dialog)
            toolbar.addAction(act_import_video)
            act_auto = QAction("Auto-Label All", self)
            act_auto.triggered.connect(self.auto_label_all)
            toolbar.addAction(act_auto)
            act_export_yolo = QAction("Export YOLO", self)
            act_export_yolo.triggered.connect(self.export_yolo)
            toolbar.addAction(act_export_yolo)
            act_export_coco = QAction("Export COCO", self)
            act_export_coco.triggered.connect(self.export_coco)
            toolbar.addAction(act_export_coco)
            act_export_voc = QAction("Export VOC", self)
            act_export_voc.triggered.connect(self.export_voc)
            toolbar.addAction(act_export_voc)
            act_save = QAction("Save Project", self)
            act_save.triggered.connect(self.save_project)
            toolbar.addAction(act_save)

            # connections
            self.thumb_panel.imageSelected.connect(self.load_image)
            self.obj_panel.objectSelected.connect(self.select_object)
            self.obj_panel.objectDeleted.connect(self.delete_object)
            self.obj_panel.classChanged.connect(self.change_object_class)
            self.canvas.objectCreated.connect(self.on_object_created)
            self.canvas.objectModified.connect(self.on_object_modified)
            self.canvas.selectionChanged.connect(self.on_canvas_selection)

            # load project if provided
            if project_path:
                self.open_project(project_path)
            else:
                # create temp project
                self.project = AnnotationProject.create("datasets/default_project", classes=self.class_names)
                self.refresh_thumbnails()

            if model_path and Path(model_path).exists():
                try:
                    self.auto_labeler = AutoLabeler(model_path=model_path, device="cpu", class_names=self.class_names)
                    self.auto_labeler.load()
                    self.statusBar.showMessage(f"Model loaded: {model_path}")
                except Exception as e:
                    self.statusBar.showMessage(f"Model load failed: {e}")

        def open_project_dialog(self):
            folder = QFileDialog.getExistingDirectory(self, "Open Project Folder")
            if folder:
                self.open_project(folder)

        def open_project(self, path: str):
            try:
                if Path(path).exists() and (Path(path)/"project.yaml").exists():
                    self.project = AnnotationProject.open(path)
                else:
                    # create new
                    self.project = AnnotationProject.create(path, classes=self.class_names)
                    self.project.import_images(path)
                self.class_names = self.project.classes
                self.refresh_thumbnails()
                self.statusBar.showMessage(f"Project opened: {path} - {len(self.project.images)} images")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to open project: {e}")

        def import_images_dialog(self):
            folder = QFileDialog.getExistingDirectory(self, "Import Images")
            if folder and self.project:
                self.project.import_images(folder)
                self.refresh_thumbnails()
                self.statusBar.showMessage(f"Imported images from {folder}")

        def import_video_dialog(self):
            file, _ = QFileDialog.getOpenFileName(self, "Import Video", "", "Videos (*.mp4 *.avi *.mkv *.mov)")
            if file and self.project:
                try:
                    count = self.project.import_video(file, fps=1.0)
                    self.refresh_thumbnails()
                    self.statusBar.showMessage(f"Extracted {count} frames from {file}")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Video import failed: {e}")

        def refresh_thumbnails(self):
            if not self.project:
                return
            self.thumb_panel.set_images(self.project.get_image_list())

        def load_image(self, path: str):
            self.current_image_path = path
            img = cv2.imread(path)
            if img is None:
                self.statusBar.showMessage(f"Failed to load {path}")
                return
            self.current_cv_image = img
            info = self.project.images.get(path)
            objs = info.annotations.objects if info else []
            self.canvas.set_image(img, objs, self.class_names if self.project else self.class_names)
            self.obj_panel.set_objects(objs, self.project.classes if self.project else self.class_names)
            self.statusBar.showMessage(f"Loaded {path} - {img.shape[1]}x{img.shape[0]} - {len(objs)} objects - Zoom: mouse wheel | Drag: create/move")

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
            # assign class based on selected in panel
            combo_idx = self.obj_panel.class_combo.currentIndex() if hasattr(self.obj_panel, 'class_combo') else 0
            if combo_idx>=0 and combo_idx < len(self.project.classes):
                obj.class_id = combo_idx
                obj.class_name = self.project.classes[combo_idx]
            info.annotations.objects.append(obj)
            self.canvas.set_image(self.current_cv_image, info.annotations.objects, self.project.classes)
            self.obj_panel.set_objects(info.annotations.objects, self.project.classes)

        def on_object_modified(self, obj):
            if not self.project or not self.current_image_path:
                return
            info = self.project.images.get(self.current_image_path)
            if not info:
                return
            # object already modified in canvas list reference
            self.obj_panel.set_objects(info.annotations.objects, self.project.classes)

        def on_canvas_selection(self, obj):
            self.obj_panel.list_widget.clearSelection()
            # select in list
            for i in range(self.obj_panel.list_widget.count()):
                item = self.obj_panel.list_widget.item(i)
                if item.data(Qt.UserRole)==obj.id:
                    self.obj_panel.list_widget.setCurrentItem(item)
                    break

        def auto_label_all(self):
            if not self.project:
                return
            if not self.auto_labeler:
                QMessageBox.warning(self, "No Model", "Load a YOLO ONNX model first via --model")
                return
            # run for all images
            for img_info in self.project.get_image_list():
                try:
                    dets = self.auto_labeler.detect_image(img_info.path)
                    # add only if not already overlapping? For simplicity add
                    # Remove existing AI boxes if desired?
                    # Keep human boxes, add AI
                    existing = img_info.annotations.objects
                    # filter previous AI?
                    # For demo, clear AI then add new
                    existing = [o for o in existing if not o.is_ai]
                    existing.extend(dets)
                    img_info.annotations.objects = existing
                except Exception as e:
                    print(f"Auto-label failed for {img_info.path}: {e}")
            if self.current_image_path:
                self.load_image(self.current_image_path)
            self.refresh_thumbnails()
            self.statusBar.showMessage("Auto-labeling complete")

        def export_yolo(self):
            if not self.project:
                return
            out = QFileDialog.getExistingDirectory(self, "Export YOLO to folder")
            if out:
                exporter = YOLOExporter(self.project.project_path, self.project.classes)
                exporter.export(self.project.get_image_list(), output_dir=out)
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

else:
    class MainWindow:
        def __init__(self, *args, **kwargs):
            raise ImportError("PySide6 not installed - cannot run GUI annotator. Install with pip install PySide6")
