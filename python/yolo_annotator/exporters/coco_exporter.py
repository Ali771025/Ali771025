from __future__ import annotations
import json
from pathlib import Path
from typing import List
import datetime
from ..core.annotation import ImageInfo

class COCOExporter:
    def __init__(self, classes: List[str]):
        self.classes = classes

    def export(self, images: List[ImageInfo], output_path: str) -> Path:
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        coco = {
            "info": {"description":"offline-yolo export","version":"1.0","year": datetime.datetime.now().year, "date_created": datetime.datetime.now().isoformat()},
            "licenses": [],
            "images": [],
            "annotations": [],
            "categories": []
        }
        for i, cname in enumerate(self.classes):
            coco["categories"].append({"id": i, "name": cname, "supercategory": "none"})

        ann_id=0
        for img_id, img_info in enumerate(images):
            coco["images"].append({
                "id": img_id,
                "file_name": Path(img_info.path).name,
                "width": img_info.width,
                "height": img_info.height
            })
            for obj in img_info.annotations.objects:
                if not obj.visible:
                    continue
                x1,y1,x2,y2 = obj.bbox_xyxy
                w = x2-x1
                h = y2-y1
                coco["annotations"].append({
                    "id": ann_id,
                    "image_id": img_id,
                    "category_id": obj.class_id,
                    "bbox": [float(x1),float(y1),float(w),float(h)],
                    "area": float(w*h),
                    "iscrowd": 0,
                    "segmentation": obj.segmentation if obj.segmentation else []
                })
                ann_id+=1

        out_path.write_text(json.dumps(coco, indent=2))
        return out_path
