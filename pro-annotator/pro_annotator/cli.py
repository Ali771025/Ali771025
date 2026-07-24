from __future__ import annotations
import sys
from pathlib import Path
import typer
from loguru import logger

app = typer.Typer(add_completion=False, help="Offline Pro Annotator 2.0 - Professional AI + LLM")

@app.command()
def main(
    project: str = typer.Option("datasets/my_dataset", "--project", "-p", help="Project folder"),
    model: str = typer.Option("models/yolov8n.onnx", "--model", "-m", help="YOLO ONNX model for auto-label"),
    sam: str = typer.Option(None, "--sam", help="SAM ONNX model"),
    llm_model: str = typer.Option(None, "--llm-model", help="Small LLM model GGUF/HF folder/ONNX: models/llm/tinyllama-1.1b-chat.gguf"),
    llm_backend: str = typer.Option("auto", "--llm-backend", help="LLM backend: auto, llama_cpp, transformers, onnx, dummy"),
    device: str = typer.Option("auto", "--device", help="Device: auto, cpu, cuda"),
    offline: bool = typer.Option(True, "--offline/--online", help="Offline mode"),
    conf: float = typer.Option(0.35, "--conf", help="Confidence threshold for auto-label"),
    wanted_classes: str = typer.Option("", "--wanted-classes", help="Only label these classes, comma separated: person,car,dog - empty = all"),
    batch_folder: str = typer.Option(None, "--batch-folder", help="Batch folder for thousands images - auto-label only wanted classes"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", help="Recursive batch folder scan"),
    headless: bool = typer.Option(False, "--headless", help="Headless batch + LLM QA + export, no GUI"),
    export_format: str = typer.Option("yolo", "--export-format", help="Export format for headless: yolo, coco, voc"),
    export_path: str = typer.Option(None, "--export-path", help="Export path for headless"),
    images: str = typer.Option(None, "--images", help="Images folder to import at start"),
    train_split: float = typer.Option(0.8, "--train-split", help="Train split ratio for dataset manager"),
    val_split: float = typer.Option(0.1, "--val-split", help="Val split ratio"),
):
    """
    Professional Offline AI Annotator with Batch + Tiny LLM

    Examples (GUI - حرفه‌ای):

      python -m pro_annotator --project datasets/my_dataset --model models/yolov8n.onnx --offline

      python -m pro_annotator --project datasets/my_dataset --model models/yolov8n.onnx --llm-model models/llm/tinyllama-1.1b-chat.gguf --offline

    Batch only wanted classes (دسته‌ای فقط کلاس‌های دلخواه):

      python -m pro_annotator --project datasets/my_dataset --model models/yolov8n.onnx \\
        --batch-folder /data/images --wanted-classes person,car --conf 0.4 --offline

    Headless batch + LLM QA + export:

      python -m pro_annotator --project datasets/my_dataset --model models/yolov8n.onnx \\
        --batch-folder /data/images --wanted-classes person,car \\
        --llm-model models/llm/tinyllama-1.1b-chat.gguf --llm-backend llama_cpp \\
        --headless --export-format yolo --export-path datasets/my_dataset/export --offline

    With Persian class names (با کلاس فارسی - نگاشت به انگلیسی داخلی) still works if classes.yaml contains Persian names.
    """
    logger.remove()
    logger.add(sys.stderr, level="INFO")

    project_path = Path(project)
    project_path.mkdir(parents=True, exist_ok=True)

    wanted_list = [x.strip() for x in wanted_classes.split(",") if x.strip()] if wanted_classes else []

    # === HEADLESS MODE ===
    if headless:
        from pro_annotator.core.project import AnnotationProject
        from pro_annotator.ai.detector import YOLODetector
        from pro_annotator.ai.batch_processor import BatchProcessor, BatchConfig
        from pro_annotator.ai.llm_analyzer import LLMAnalyzer
        from pro_annotator.exporters import YOLOExporter, COCOExporter, VOCExporter
        from pro_annotator.core.dataset import DatasetManager

        # open or create project
        if (project_path / "project.yaml").exists():
            proj = AnnotationProject.open(str(project_path))
        else:
            proj = AnnotationProject.create(str(project_path))
        logger.info(f"Project: {proj.project_path} - {len(proj.images)} images - classes: {proj.classes}")

        if images:
            cnt = proj.import_images(images, recursive=recursive)
            logger.info(f"Imported {cnt} from {images}")

        if wanted_list:
            proj.set_wanted_classes(wanted_list)
            logger.info(f"Wanted classes set to {wanted_list}")

        detector = None
        if model and Path(model).exists():
            detector = YOLODetector(model_path=model, device=device, conf_thres=conf, wanted_classes=wanted_list)
            try:
                detector.load()
                detector.warmup(3)
                logger.info(f"YOLO loaded {model}")
            except Exception as e:
                logger.error(f"YOLO load failed: {e}")
                detector = None

        # batch folder processing
        if batch_folder and detector:
            bp = BatchProcessor(proj, detector)
            cfg = BatchConfig(
                input_folder=batch_folder,
                recursive=recursive,
                wanted_classes=wanted_list,
                conf_thres=conf,
                save_after=50
            )
            result = bp.process_folder(cfg)
            logger.info(f"Batch result: {result.processed}/{result.total_images} in {result.elapsed_sec:.1f}s")

        # LLM QA
        if llm_model:
            llm = LLMAnalyzer(model_path=llm_model, backend=llm_backend, device="cpu")
            llm.load()
            report = llm.analyze_dataset(proj.get_image_list(), proj.classes)
            logger.info(f"LLM Dataset Report: {report.description}")
            logger.info(f"Issues: {report.issues_summary}")
            # save report
            import json
            report_path = project_path / "llm_report.json"
            report_path.write_text(json.dumps({
                "description": report.description,
                "class_distribution": report.class_distribution,
                "issues": report.issues_summary,
                "suggestions": [s.__dict__ for s in report.suggestions]
            }, indent=2, ensure_ascii=False))
            logger.info(f"LLM report saved to {report_path}")

        # dataset manager stats + split info
        dm = DatasetManager(proj.classes)
        stats = dm.compute_stats(proj.get_image_list())
        logger.info(f"Stats: {stats['total_images']} images, {stats['total_objects']} objects, distribution: {stats['class_distribution']}")
        # save stats
        import json
        (project_path / "dataset_stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")

        # export
        exp_path = export_path or str(project_path / f"export_{export_format}")
        if export_format == "yolo":
            ex = YOLOExporter(project_path, proj.classes)
            out = ex.export(proj.get_image_list(), output_dir=exp_path)
            logger.info(f"Exported YOLO to {out}")
        elif export_format == "coco":
            ex = COCOExporter(proj.classes)
            out_file = Path(exp_path) / "coco.json" if not str(exp_path).endswith(".json") else Path(exp_path)
            out = ex.export(proj.get_image_list(), str(out_file))
            logger.info(f"Exported COCO to {out}")
        elif export_format == "voc":
            ex = VOCExporter(proj.classes)
            out = ex.export(proj.get_image_list(), exp_path)
            logger.info(f"Exported VOC to {out}")

        proj.save()
        logger.info("Headless done")
        return

    # === GUI MODE ===
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        logger.error("PySide6 not installed. Install with: pip install PySide6, or use --headless")
        sys.exit(1)

    from pro_annotator.ui.main_window import MainWindow
    from pro_annotator.ui.styles import DARK_STYLE

    qapp = QApplication(sys.argv)
    qapp.setStyle("Fusion")
    qapp.setStyleSheet(DARK_STYLE)

    # optional wanted classes arg passed to main window
    window = MainWindow(
        project_path=str(project_path),
        model_path=model,
        llm_model_path=llm_model,
        offline=offline,
        wanted_classes=wanted_classes
    )
    # if batch folder provided in GUI mode, set it in batch panel
    if batch_folder:
        try:
            window.batch_panel.set_folder(batch_folder)
        except Exception:
            pass

    if llm_model:
        try:
            window.llm_panel.set_model_path(llm_model)
        except Exception:
            pass

    window.show()
    sys.exit(qapp.exec())

if __name__ == "__main__":
    app()
