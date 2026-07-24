from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple
import uuid

@dataclass
class AnnotationObject:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    class_id: int = 0
    class_name: str = "object"
    bbox_xyxy: Tuple[float,float,float,float] = (0,0,0,0)  # x1,y1,x2,y2
    bbox_xywh_norm: Tuple[float,float,float,float] = (0,0,0,0)
    confidence: float = 1.0
    is_ai: bool = False
    is_reviewed: bool = False
    track_id: int = -1
    polygon: List[Tuple[float,float]] = field(default_factory=list)  # optional polygon points normalized or pixel?
    segmentation: Optional[List[List[float]]] = None  # COCO segmentation
    area: float = 0.0
    visible: bool = True

    def update_norm(self, img_w: int, img_h: int):
        x1,y1,x2,y2 = self.bbox_xyxy
        cx = ((x1+x2)/2)/img_w if img_w else 0
        cy = ((y1+y2)/2)/img_h if img_h else 0
        w = (x2-x1)/img_w if img_w else 0
        h = (y2-y1)/img_h if img_h else 0
        self.bbox_xywh_norm = (cx,cy,w,h)
        self.area = (x2-x1)*(y2-y1)

@dataclass
class ImageAnnotations:
    image_path: str = ""
    image_id: str = ""
    width: int = 0
    height: int = 0
    objects: List[AnnotationObject] = field(default_factory=list)
    reviewed: bool = False
    status: str = "not-reviewed"  # not-reviewed, reviewed, rejected

@dataclass
class ImageInfo:
    path: str
    width: int
    height: int
    annotations: ImageAnnotations
