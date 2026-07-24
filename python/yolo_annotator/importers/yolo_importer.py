from __future__ import annotations
from pathlib import Path
from typing import List, Dict
import cv2
from ..core.annotation import ImageInfo, ImageAnnotations, AnnotationObject

class YOLOImporter:
    def __init__(self, classes: List[str]):
        self.classes = classes

    def import_folder(self, images_dir: str, labels_dir: str) -> Dict[str, ImageInfo]:
        images_dir = Path(images_dir)
        labels_dir = Path(labels_dir)
        result = {}
        exts = {".jpg",".jpeg",".png",".bmp",".webp"}
        for img_file in images_dir.rglob("*"):
            if img_file.suffix.lower() not in exts:
                continue
            label_file = labels_dir / f"{img_file.stem}.txt"
            img = cv2.imread(str(img_file))
            h,w = img.shape[:2] if img is not None else (0,0)
            ann = ImageAnnotations(image_path=str(img_file), image_id=img_file.stem, width=w, height=h)
            if label_file.exists():
                for line in label_file.read_text().strip().splitlines():
                    if not line.strip():
                        continue
                    parts = line.split()
                    if len(parts)<5:
                        continue
                    cid = int(parts[0])
                    cx,cy,bw,bh = map(float, parts[1:5])
                    x1 = (cx - bw/2)*w
                    y1 = (cy - bh/2)*h
                    x2 = (cx + bw/2)*w
                    y2 = (cy + bh/2)*h
                    cname = self.classes[cid] if cid < len(self.classes) else str(cid)
                    obj = AnnotationObject(class_id=cid, class_name=cname, bbox_xyxy=(x1,y1,x2,y2), bbox_xywh_norm=(cx,cy,bw,bh), confidence=1.0, is_ai=False)
                    ann.objects.append(obj)
            result[str(img_file)] = ImageInfo(path=str(img_file), width=w, height=h, annotations=ann)
        return result
