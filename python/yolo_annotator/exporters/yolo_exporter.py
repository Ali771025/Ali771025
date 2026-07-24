from __future__ import annotations
from pathlib import Path
from typing import List
import yaml
from ..core.annotation import ImageInfo

class YOLOExporter:
    def __init__(self, project_path: str, classes: List[str]):
        self.project_path = Path(project_path)
        self.classes = classes

    def export(self, images: List[ImageInfo], output_dir: str = None, split: str = None):
        out_dir = Path(output_dir) if output_dir else self.project_path / "export_yolo"
        labels_dir = out_dir / "labels"
        images_dir = out_dir / "images"
        labels_dir.mkdir(parents=True, exist_ok=True)
        # images may be symlink or copy list only
        for img_info in images:
            stem = Path(img_info.path).stem
            label_file = labels_dir / f"{stem}.txt"
            with open(label_file, "w") as f:
                for obj in img_info.annotations.objects:
                    if not obj.visible:
                        continue
                    cx,cy,w,h = obj.bbox_xywh_norm
                    # clip
                    cx = max(0,min(1,cx)); cy=max(0,min(1,cy)); w=max(0,min(1,w)); h=max(0,min(1,h))
                    f.write(f"{obj.class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")
        # classes.yaml
        data_yaml = {
            "path": str(out_dir),
            "train": "images",
            "val": "images",
            "names": {i:name for i,name in enumerate(self.classes)}
        }
        (out_dir / "dataset.yaml").write_text(yaml.safe_dump(data_yaml))
        return out_dir
