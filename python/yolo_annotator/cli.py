from __future__ import annotations
import sys
from pathlib import Path
import typer
from loguru import logger

app = typer.Typer(add_completion=False, help="Offline YOLO Annotator")

@app.command()
def main(
    project: str = typer.Option("datasets/my_dataset", "--project", "-p", help="Project folder"),
    model: str = typer.Option("models/yolov8n.onnx", "--model", "-m", help="YOLO ONNX model for auto-label"),
    sam: str = typer.Option(None, "--sam", help="SAM ONNX model for segmentation assistance"),
    device: str = typer.Option("auto", "--device", help="Device: auto, cpu, cuda"),
    offline: bool = typer.Option(True, "--offline/--online", help="Offline mode"),
    conf: float = typer.Option(0.3, "--conf", help="Confidence threshold for auto-label"),
    headless: bool = typer.Option(False, "--headless", help="Run without GUI, just auto-label and export"),
    export_format: str = typer.Option("yolo", "--export-format", help="Export format for headless: yolo, coco, voc"),
    export_path: str = typer.Option(None, "--export-path", help="Export path for headless"),
    images: str = typer.Option(None, "--images", help="Images folder to import in headless mode"),
):
    """
    Professional offline AI-assisted annotation software
    Example:
      python -m yolo_annotator --project datasets/my_dataset --model models/yolov8n.onnx --offline
      python -m yolo_annotator --project datasets/my_dataset --model models/yolov8n.onnx --headless --images data/ --export-format yolo --export-path out/
    """
    logger.remove()
    logger.add(sys.stderr, level="INFO")

    project_path = Path(project)
    project_path.mkdir(parents=True, exist_ok=True)

    if headless:
        # headless auto-label workflow
        from yolo_annotator.core.project import AnnotationProject
        from yolo_annotator.ai.auto_labeler import AutoLabeler
        from yolo_annotator.exporters import YOLOExporter, COCOExporter, VOCExporter

        if not project_path.exists():
            proj = AnnotationProject.create(str(project_path))
        else:
            try:
                proj = AnnotationProject.open(str(project_path))
            except:
                proj = AnnotationProject.create(str(project_path))

        if images:
            proj.import_images(images)
            logger.info(f"Imported images from {images}: {len(proj.images)} total")

        if model and Path(model).exists():
            auto = AutoLabeler(model_path=model, device=device, conf_thres=conf)
            try:
                auto.load()
                logger.info(f"Auto-labeler loaded: {model}")
                for img_info in proj.get_image_list():
                    dets = auto.detect_image(img_info.path)
                    # keep only AI? For headless, replace
                    img_info.annotations.objects = dets
                logger.info(f"Auto-labeled {len(proj.get_image_list())} images")
            except Exception as e:
                logger.error(f"Auto-label failed: {e}")
                sys.exit(1)
        else:
            logger.warning(f"Model not found: {model}")

        # export
        exp_path = export_path or str(project_path / f"export_{export_format}")
        if export_format == "yolo":
            exporter = YOLOExporter(project_path, proj.classes)
            out = exporter.export(proj.get_image_list(), output_dir=exp_path)
            logger.info(f"Exported YOLO to {out}")
        elif export_format == "coco":
            exporter = COCOExporter(proj.classes)
            out_file = Path(exp_path) / "coco.json" if Path(exp_path).is_dir() or not exp_path.endswith(".json") else Path(exp_path)
            out = exporter.export(proj.get_image_list(), str(out_file))
            logger.info(f"Exported COCO to {out}")
        elif export_format == "voc":
            exporter = VOCExporter(proj.classes)
            out = exporter.export(proj.get_image_list(), exp_path)
            logger.info(f"Exported VOC to {out}")
        else:
            logger.error(f"Unknown export format: {export_format}")
        proj.save()
        return

    # GUI mode
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        logger.error("PySide6 not installed. Install with: pip install PySide6. Or use --headless mode")
        sys.exit(1)

    from yolo_annotator.ui.main_window import MainWindow

    qapp = QApplication(sys.argv)
    qapp.setStyle("Fusion")
    # dark theme
    try:
        # simple dark stylesheet
        qapp.setStyleSheet("""
        QWidget { background-color: #2b2b2b; color: #e0e0e0; }
        QMainWindow { background-color: #2b2b2b; }
        QPushButton { background-color: #3c3c3c; border: 1px solid #555; padding: 5px; }
        QPushButton:hover { background-color: #4c4c4c; }
        QListWidget { background-color: #353535; }
        QToolBar { background-color: #3c3c3c; }
        QLabel { color: #e0e0e0; }
        """)
    except Exception:
        pass

    window = MainWindow(project_path=str(project_path), model_path=model, offline=offline)
    window.show()
    sys.exit(qapp.exec())

if __name__ == "__main__":
    app()
