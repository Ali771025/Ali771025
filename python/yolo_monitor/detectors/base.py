from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import numpy as np

@dataclass
class Detection:
    class_id: int
    class_name: str
    confidence: float
    xyxy: Tuple[float,float,float,float]  # x1,y1,x2,y2
    xywh: Tuple[float,float,float,float]  # x,y,w,h
    xywh_norm: Tuple[float,float,float,float]  # cx,cy,w,h normalized 0-1
    center: Tuple[float,float]
    area: float
    aspect_ratio: float
    track_id: int = -1
    frame_id: int = 0
    model_name: str = ""
    inference_time_ms: float = 0.0

@dataclass
class FrameResult:
    frame_id: int
    width: int
    height: int
    detections: List[Detection] = field(default_factory=list)
    inference_time_ms: float = 0.0
    timestamp_unix: float = 0.0

class BaseDetector(ABC):
    def __init__(self, model_path: str, device: str = "cpu", imgsz: int = 640, conf_thres: float = 0.35, iou_thres: float = 0.45, max_det: int = 300, classes: Optional[List[int]] = None, half: bool = False):
        self.model_path = model_path
        self.device = device
        self.imgsz = imgsz
        self.conf_thres = conf_thres
        self.iou_thres = iou_thres
        self.max_det = max_det
        self.classes = classes or []
        self.half = half
        self.class_names: List[str] = []
        self.model_name = model_path

    @abstractmethod
    def load(self):
        pass

    @abstractmethod
    def warmup(self, iters: int = 10):
        pass

    @abstractmethod
    def detect(self, frame: np.ndarray, frame_id: int = 0) -> FrameResult:
        pass

    def shutdown(self):
        pass

def letterbox(img: np.ndarray, new_shape: int = 640, color=(114,114,114), stride: int = 32):
    h,w = img.shape[:2]
    if isinstance(new_shape,int):
        new_shape = (new_shape,new_shape)
    r = min(new_shape[0]/h, new_shape[1]/w)
    new_unpad = (int(round(w*r)), int(round(h*r)))
    dw, dh = new_shape[1]-new_unpad[0], new_shape[0]-new_unpad[1]
    dw/=2; dh/=2
    resized = cv2_resize(img,new_unpad)
    top,bottom = int(round(dh-0.1)), int(round(dh+0.1))
    left,right = int(round(dw-0.1)), int(round(dw+0.1))
    import cv2
    out = cv2.copyMakeBorder(resized, top,bottom,left,right, cv2.BORDER_CONSTANT, value=color)
    return out, (r, (dw,dh))

def cv2_resize(img, size):
    import cv2
    return cv2.resize(img, size, interpolation=cv2.INTER_LINEAR)

def nms_boxes(boxes: np.ndarray, scores: np.ndarray, iou_thres: float = 0.45, max_det: int = 300):
    # boxes Nx4 xyxy
    # scores N
    import cv2
    # opencv NMS expects boxes as [x,y,w,h] ?
    # We'll implement own NMS using cv2.dnn.NMSBoxes or pure python.
    if len(boxes)==0:
        return []
    # convert to tlwh for cv2 NMSBoxes
    # but cv2 NMSBoxes needs list of [x,y,w,h]
    tlwh = []
    for b in boxes:
        x1,y1,x2,y2 = b
        tlwh.append([float(x1),float(y1),float(x2-x1),float(y2-y1)])
    indices = cv2.dnn.NMSBoxes(tlwh, scores.tolist(), score_threshold=0.0, nms_threshold=iou_thres)
    if len(indices)==0:
        return []
    indices = indices.flatten() if hasattr(indices,'flatten') else [i[0] for i in indices]
    # sort by score descending, keep max_det
    sorted_idx = sorted(indices, key=lambda i: scores[i], reverse=True)[:max_det]
    return sorted_idx
