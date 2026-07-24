from __future__ import annotations
import time
import threading
import queue
from pathlib import Path
from typing import List, Callable, Optional, Set, Dict
import cv2
from loguru import logger
from tqdm import tqdm
from dataclasses import dataclass, field

from ..core.annotation import ImageInfo, ImageAnnotations, AnnotationObject
from ..core.project import AnnotationProject
from .detector import YOLODetector

@dataclass
class BatchConfig:
    input_folder: str
    recursive: bool = True
    wanted_classes: List[str] = None
    conf_thres: float = 0.35
    iou_thres: float = 0.45
    max_det: int = 300
    save_after: int = 50
    overwrite_ai: bool = True
    keep_human: bool = True
    max_images: int = 0

@dataclass
class BatchResult:
    total_images: int = 0
    processed: int = 0
    labeled: int = 0
    skipped: int = 0
    errors: int = 0
    elapsed_sec: float = 0.0
    per_image: List[Dict] = field(default_factory=list)

class BatchProcessor:
    def __init__(self, project: AnnotationProject, detector: YOLODetector):
        self.project = project
        self.detector = detector
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.progress_callback: Optional[Callable[[int,int,str],None]] = None
        self.result_callback: Optional[Callable[[BatchResult],None]] = None

    def set_wanted_classes(self, wanted: List[str]):
        self.project.set_wanted_classes(wanted)
        self.detector.set_wanted_classes(wanted)
        logger.info(f"Batch wanted classes set to {wanted}")

    def process_folder(self, config: BatchConfig, progress_cb: Callable = None) -> BatchResult:
        self.set_wanted_classes(config.wanted_classes or [])
        input_path = Path(config.input_folder)
        if not input_path.exists():
            raise FileNotFoundError(f"Input folder not found: {config.input_folder}")
        exts = {".jpg",".jpeg",".png",".bmp",".webp",".tiff"}
        if config.recursive:
            files = [f for f in input_path.rglob("*") if f.suffix.lower() in exts]
        else:
            files = [f for f in input_path.glob("*") if f.suffix.lower() in exts]
        if config.max_images > 0:
            files = files[:config.max_images]
        total = len(files)
        result = BatchResult(total_images=total)
        logger.info(f"Batch processing {total} images from {config.input_folder}, wanted={config.wanted_classes}, conf={config.conf_thres}")
        t0 = time.time()
        for idx, f in enumerate(tqdm(files, desc="Batch labeling")):
            if self.stop_event.is_set():
                break
            try:
                img = cv2.imread(str(f))
                if img is None:
                    result.skipped+=1
                    continue
                h,w = img.shape[:2]
                detections = self.detector.detect_image(img)
                if self.project.wanted_classes or self.project.wanted_class_ids:
                    detections = [d for d in detections if self.project.is_wanted(d.class_id, d.class_name)]
                path_str = str(f)
                if path_str not in self.project.images:
                    ann = ImageAnnotations(image_path=path_str, image_id=f.stem, width=w, height=h)
                    self.project.images[path_str] = ImageInfo(path=path_str, width=w, height=h, annotations=ann)
                info = self.project.images[path_str]
                if config.overwrite_ai:
                    if config.keep_human:
                        info.annotations.objects = [o for o in info.annotations.objects if not o.is_ai]
                    else:
                        info.annotations.objects = []
                info.annotations.objects.extend(detections)
                info.width = w
                info.height = h
                info.annotations.width = w
                info.annotations.height = h
                result.processed+=1
                result.labeled+=1
                result.per_image.append({"path": str(f), "detections": len(detections)})
                if progress_cb:
                    progress_cb(idx+1, total, str(f))
                if (idx+1) % config.save_after == 0:
                    self.project.save()
                    logger.info(f"Autosaved after {idx+1} images")
            except Exception as e:
                logger.error(f"Batch error {f}: {e}")
                result.errors+=1
                result.per_image.append({"path": str(f), "error": str(e)})
        result.elapsed_sec = time.time() - t0
        self.project.save()
        logger.info(f"Batch finished: {result.processed}/{total} in {result.elapsed_sec:.1f}s, errors {result.errors}")
        if self.result_callback:
            self.result_callback(result)
        return result

    def process_async(self, config: BatchConfig, progress_cb: Callable = None, done_cb: Callable = None):
        self.stop_event.clear()
        self.progress_callback = progress_cb
        self.result_callback = done_cb
        def run():
            res = self.process_folder(config, progress_cb=progress_cb)
            if done_cb:
                done_cb(res)
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        return self.thread

    def stop(self):
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
