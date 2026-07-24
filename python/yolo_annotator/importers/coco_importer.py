from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List
import cv2
from ..core.annotation import ImageInfo, ImageAnnotations, AnnotationObject

class COCOImporter:
    def import_file(self, coco_path: str, images_base_dir: str = None) -> Dict[str, ImageInfo]:
        data = json.loads(Path(coco_path).read_text())
        categories = {c["id"]: c["name"] for c in data.get("categories",[])}
        images = {img["id"]: img for img in data.get("images",[])}
        result = {}
        base = Path(images_base_dir) if images_base_dir else Path(coco_path).parent
        # group annotations by image
        ann_by_image = {}
        for ann in data.get("annotations",[]):
            iid = ann["image_id"]
            ann_by_image.setdefault(iid, []).append(ann)

        for img_id, img_meta in images.items():
            file_name = img_meta["file_name"]
            img_path = base / file_name
            if not img_path.exists():
                # try absolute
                img_path = Path(file_name)
            w = img_meta.get("width",0)
            h = img_meta.get("height",0)
            if img_path.exists() and (w==0 or h==0):
                try:
                    cv_img = cv2.imread(str(img_path))
                    if cv_img is not None:
                        h,w = cv_img.shape[:2]
                except Exception:
                    pass
            ann = ImageAnnotations(image_path=str(img_path), image_id=str(img_id), width=w, height=h)
            for a in ann_by_image.get(img_id,[]):
                cid = a["category_id"]
                cname = categories.get(cid, str(cid))
                # coco bbox is x,y,w,h
                x,y,bw,bh = a["bbox"]
                x1,y1,x2,y2 = x, y, x+bw, y+bh
                cx = (x1+x2)/2/w if w else 0
                cy = (y1+y2)/2/h if h else 0
                nw = bw/w if w else 0
                nh = bh/h if h else 0
                obj = AnnotationObject(class_id=cid, class_name=cname, bbox_xyxy=(x1,y1,x2,y2), bbox_xywh_norm=(cx,cy,nw,nh), confidence=1.0)
                ann.objects.append(obj)
            result[str(img_path)] = ImageInfo(path=str(img_path), width=w, height=h, annotations=ann)
        return result
