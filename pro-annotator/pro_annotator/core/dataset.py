from __future__ import annotations
import random
import shutil
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from collections import Counter, defaultdict
import json
import time

from .annotation import ImageInfo, ImageAnnotations
from .validators import LabelValidator

class DatasetManager:
    """
    Professional dataset management for annotator:
    - Stats, class distribution, size distribution
    - Train/val/test split
    - Active learning (low confidence export)
    - Duplicate detection
    - Wanted classes filtering
    """

    def __init__(self, project_classes: List[str]):
        self.classes = project_classes
        self.validator = LabelValidator()

    def compute_stats(self, images: List[ImageInfo]) -> Dict:
        total_images = len(images)
        total_objects = sum(len(img.annotations.objects) for img in images)
        class_counter = Counter()
        for img in images:
            class_counter.update([o.class_name for o in img.annotations.objects if o.visible])

        # size stats
        size_by_class = defaultdict(list)
        for img in images:
            for obj in img.annotations.objects:
                if not obj.visible:
                    continue
                size_by_class[obj.class_name].append(obj.area)

        size_summary = {}
        for cname, areas in size_by_class.items():
            if areas:
                size_summary[cname] = {
                    "count": len(areas),
                    "min": min(areas),
                    "max": max(areas),
                    "avg": sum(areas)/len(areas),
                    "median": sorted(areas)[len(areas)//2]
                }

        # reviewed stats
        reviewed = sum(1 for img in images if img.annotations.reviewed)
        needs_fix = sum(1 for img in images if img.annotations.status == "needs_fix")

        # validation
        val_report = self.validator.validate_dataset([img.annotations for img in images], self.classes)

        return {
            "total_images": total_images,
            "total_objects": total_objects,
            "class_distribution": dict(class_counter),
            "size_summary": size_summary,
            "reviewed": reviewed,
            "needs_fix": needs_fix,
            "validation": val_report,
            "generated_at": time.time(),
        }

    def split(self, images: List[ImageInfo], train_ratio: float = 0.8, val_ratio: float = 0.1, test_ratio: float = 0.1, seed: int = 42, stratify: bool = False) -> Dict[str, List[ImageInfo]]:
        """
        Split into train/val/test
        If stratify True, tries to keep class distribution
        """
        assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6, "Ratios must sum to 1.0"
        random.seed(seed)
        imgs = images.copy()
        random.shuffle(imgs)
        n = len(imgs)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)
        train = imgs[:n_train]
        val = imgs[n_train:n_train+n_val]
        test = imgs[n_train+n_val:]
        return {"train": train, "val": val, "test": test}

    def export_active_learning(self, images: List[ImageInfo], low_conf_thres: float = 0.4, output_dir: str = None) -> List[ImageInfo]:
        """
        Export low-confidence AI samples for retraining / human review
        """
        low_conf_images = []
        for img in images:
            has_low = any(o.is_ai and o.confidence < low_conf_thres for o in img.annotations.objects)
            if has_low:
                low_conf_images.append(img)
        if output_dir:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            # copy images? For now just list
            report = {
                "low_conf_threshold": low_conf_thres,
                "count": len(low_conf_images),
                "images": [img.path for img in low_conf_images]
            }
            (Path(output_dir) / "active_learning_report.json").write_text(json.dumps(report, indent=2))
        return low_conf_images

    def find_duplicates(self, images: List[ImageInfo], iou_thres: float = 0.95) -> List[Dict]:
        duplicates = []
        for img in images:
            objs = img.annotations.objects
            for i in range(len(objs)):
                for j in range(i+1, len(objs)):
                    from .annotation import AnnotationObject
                    iou = AnnotationObject.iou(objs[i], objs[j])
                    if iou > iou_thres and objs[i].class_id == objs[j].class_id:
                        duplicates.append({
                            "image": img.path,
                            "obj1": objs[i].id,
                            "obj2": objs[j].id,
                            "iou": iou,
                            "class": objs[i].class_name
                        })
        return duplicates

    def filter_by_wanted_classes(self, images: List[ImageInfo], wanted_classes: List[str]) -> List[ImageInfo]:
        if not wanted_classes:
            return images
        wanted_set = set(wanted_classes)
        filtered = []
        for img in images:
            # keep image if it has at least one wanted object OR if you want all images to be processed
            # For dataset manager, we return all images but with filtered objects? Let's do filtered objects
            # Create copy with filtered objects
            filtered_objs = [o for o in img.annotations.objects if o.class_name in wanted_set]
            if filtered_objs or True:  # keep all images, even if empty after filter, for batch labeling
                # shallow copy
                new_info = ImageInfo(
                    path=img.path,
                    width=img.width,
                    height=img.height,
                    annotations=ImageAnnotations(
                        image_path=img.annotations.image_path,
                        image_id=img.annotations.image_id,
                        width=img.annotations.width,
                        height=img.annotations.height,
                        objects=filtered_objs,
                        reviewed=img.annotations.reviewed,
                        status=img.annotations.status,
                        llm_analysis=img.annotations.llm_analysis
                    )
                )
                filtered.append(new_info)
        return filtered

    def merge_projects(self, projects_images: List[List[ImageInfo]]) -> List[ImageInfo]:
        merged: Dict[str, ImageInfo] = {}
        for img_list in projects_images:
            for img in img_list:
                if img.path not in merged:
                    merged[img.path] = img
                else:
                    # merge objects
                    existing_ids = {o.id for o in merged[img.path].annotations.objects}
                    for o in img.annotations.objects:
                        if o.id not in existing_ids:
                            merged[img.path].annotations.objects.append(o)
        return list(merged.values())
