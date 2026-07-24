from __future__ import annotations
import threading
import queue
from pathlib import Path
from typing import List, Optional, Callable
import cv2
import numpy as np

from yolo_monitor.detectors import create_detector
from yolo_annotator.core.annotation import AnnotationObject
from yolo_monitor.utils.geometry import xyxy_to_xywh, xyxy_to_cxcywh_norm

class AutoLabeler:
    def __init__(self, model_path: str, device: str = "cpu", conf_thres: float = 0.3, iou_thres: float = 0.45, class_filter: List[int] = None, class_names: List[str] = None):
        self.model_path = model_path
        self.device = device
        self.conf_thres = conf_thres
        self.iou_thres = iou_thres
        self.class_filter = class_filter or []
        self.class_names = class_names or []
        self.detector = create_detector(model_path=model_path, backend="auto", device=device, conf_thres=conf_thres, iou_thres=iou_thres, classes=self.class_filter)
        self.queue = queue.Queue()
        self.result_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.thread = None

    def load(self):
        self.detector.load()
        self.detector.warmup(5)
        if not self.class_names:
            self.class_names = self.detector.class_names

    def start_background(self):
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def stop_background(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=1.0)

    def _worker(self):
        while not self.stop_event.is_set():
            try:
                task = self.queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                image_path, callback = task
                dets = self.detect_image(image_path)
                self.result_queue.put((image_path, dets))
                if callback:
                    callback(image_path, dets)
            except Exception as e:
                print(f"AutoLabeler error: {e}")
            finally:
                self.queue.task_done()

    def queue_image(self, image_path: str, callback: Callable = None):
        self.queue.put((image_path, callback))

    def detect_image(self, image_path: str) -> List[AnnotationObject]:
        img = cv2.imread(image_path)
        if img is None:
            return []
        h,w = img.shape[:2]
        result = self.detector.detect(img)
        objects = []
        for det in result.detections:
            x1,y1,x2,y2 = det.xyxy
            cx = ((x1+x2)/2)/w
            cy = ((y1+y2)/2)/h
            bw = (x2-x1)/w
            bh = (y2-y1)/h
            obj = AnnotationObject(
                class_id=det.class_id,
                class_name=det.class_name,
                bbox_xyxy=(float(x1),float(y1),float(x2),float(y2)),
                bbox_xywh_norm=(float(cx),float(cy),float(bw),float(bh)),
                confidence=float(det.confidence),
                is_ai=True,
                is_reviewed=False,
                area=float((x2-x1)*(y2-y1))
            )
            objects.append(obj)
        return objects

    def detect_cv_image(self, img: np.ndarray) -> List[AnnotationObject]:
        h,w = img.shape[:2]
        result = self.detector.detect(img)
        objects=[]
        for det in result.detections:
            x1,y1,x2,y2 = det.xyxy
            cx = ((x1+x2)/2)/w
            cy = ((y1+y2)/2)/h
            bw = (x2-x1)/w
            bh = (y2-y1)/h
            obj = AnnotationObject(
                class_id=det.class_id,
                class_name=det.class_name,
                bbox_xyxy=(float(x1),float(y1),float(x2),float(y2)),
                bbox_xywh_norm=(float(cx),float(cy),float(bw),float(bh)),
                confidence=float(det.confidence),
                is_ai=True,
                area=float((x2-x1)*(y2-y1))
            )
            objects.append(obj)
        return objects
