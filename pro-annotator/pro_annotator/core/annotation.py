from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
import uuid
import time

@dataclass
class AnnotationObject:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    class_id: int = 0
    class_name: str = "object"
    bbox_xyxy: Tuple[float,float,float,float] = (0,0,0,0)  # x1,y1,x2,y2 pixel
    bbox_xywh_norm: Tuple[float,float,float,float] = (0,0,0,0)  # cx,cy,w,h normalized
    confidence: float = 1.0
    is_ai: bool = False
    is_reviewed: bool = False
    track_id: int = -1
    polygon: List[Tuple[float,float]] = field(default_factory=list)  # [[x,y],...] pixel
    segmentation: Optional[List[List[float]]] = None  # COCO format
    area: float = 0.0
    visible: bool = True
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())
    attributes: Dict[str, Any] = field(default_factory=dict)  # custom attributes for LLM

    def update_norm(self, img_w: int, img_h: int):
        x1,y1,x2,y2 = self.bbox_xyxy
        cx = ((x1+x2)/2)/img_w if img_w else 0
        cy = ((y1+y2)/2)/img_h if img_h else 0
        w = (x2-x1)/img_w if img_w else 0
        h = (y2-y1)/img_h if img_h else 0
        self.bbox_xywh_norm = (cx,cy,w,h)
        self.area = max(0.0, x2-x1) * max(0.0, y2-y1)
        self.updated_at = time.time()

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "bbox_xyxy": list(self.bbox_xyxy),
            "bbox_norm": list(self.bbox_xywh_norm),
            "conf": self.confidence,
            "is_ai": self.is_ai,
            "polygon": self.polygon,
            "area": self.area,
            "visible": self.visible,
        }

    @staticmethod
    def iou(a: "AnnotationObject", b: "AnnotationObject") -> float:
        x1 = max(a.bbox_xyxy[0], b.bbox_xyxy[0])
        y1 = max(a.bbox_xyxy[1], b.bbox_xyxy[1])
        x2 = min(a.bbox_xyxy[2], b.bbox_xyxy[2])
        y2 = min(a.bbox_xyxy[3], b.bbox_xyxy[3])
        if x2 <= x1 or y2 <= y1:
            return 0.0
        inter = (x2-x1)*(y2-y1)
        area_a = max(0, a.bbox_xyxy[2]-a.bbox_xyxy[0]) * max(0, a.bbox_xyxy[3]-a.bbox_xyxy[1])
        area_b = max(0, b.bbox_xyxy[2]-b.bbox_xyxy[0]) * max(0, b.bbox_xyxy[3]-b.bbox_xyxy[1])
        union = area_a + area_b - inter
        if union <= 0:
            return 0.0
        return inter/union

@dataclass
class ImageAnnotations:
    image_path: str = ""
    image_id: str = ""
    width: int = 0
    height: int = 0
    objects: List[AnnotationObject] = field(default_factory=list)
    reviewed: bool = False
    status: str = "not-reviewed"  # not-reviewed, reviewed, rejected, needs_fix
    llm_analysis: Optional[Dict[str,Any]] = None  # last LLM analysis result
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())

    def get_by_class(self, class_name: str) -> List[AnnotationObject]:
        return [o for o in self.objects if o.class_name == class_name]

    def count_by_class(self) -> Dict[str,int]:
        from collections import Counter
        return dict(Counter([o.class_name for o in self.objects if o.visible]))

@dataclass
class ImageInfo:
    path: str
    width: int = 0
    height: int = 0
    annotations: ImageAnnotations = None
    thumbnail_path: Optional[str] = None

    def __post_init__(self):
        if self.annotations is None:
            self.annotations = ImageAnnotations(image_path=self.path, width=self.width, height=self.height)
