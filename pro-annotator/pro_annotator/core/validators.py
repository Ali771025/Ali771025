from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Tuple, Any
from .annotation import AnnotationObject, ImageAnnotations

@dataclass
class ValidationIssue:
    type: str  # duplicate, tiny, out_of_bounds, overlap, class_mismatch, low_conf, negative
    severity: str  # info, warning, error
    message: str
    object_id: str = ""
    details: Dict[str,Any] = None

    def to_dict(self):
        return {
            "type": self.type,
            "severity": self.severity,
            "message": self.message,
            "object_id": self.object_id,
            "details": self.details or {}
        }

class LabelValidator:
    """
    Professional heuristic validator for object detection labels.
    Used by both Dummy LLM backend and as pre-filter before LLM.
    """
    def __init__(self,
                 min_box_size: int = 8,
                 max_overlap_iou: float = 0.95,
                 min_conf: float = 0.15,
                 check_oob: bool = True,
                 check_tiny: bool = True,
                 check_duplicate: bool = True):
        self.min_box_size = min_box_size
        self.max_overlap_iou = max_overlap_iou
        self.min_conf = min_conf
        self.check_oob = check_oob
        self.check_tiny = check_tiny
        self.check_duplicate = check_duplicate

    def validate_image(self, ann: ImageAnnotations) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        w, h = ann.width, ann.height
        objs = ann.objects

        for obj in objs:
            if not obj.visible:
                continue
            x1,y1,x2,y2 = obj.bbox_xyxy
            bw = x2 - x1
            bh = y2 - y1

            # negative size
            if bw <= 0 or bh <= 0:
                issues.append(ValidationIssue(
                    type="negative",
                    severity="error",
                    message=f"Box negative size {obj.class_name} [{x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}]",
                    object_id=obj.id,
                    details={"bbox": obj.bbox_xyxy}
                ))
                continue

            # out of bounds
            if self.check_oob:
                if x1 < -5 or y1 < -5 or x2 > w+5 or y2 > h+5:
                    issues.append(ValidationIssue(
                        type="out_of_bounds",
                        severity="warning",
                        message=f"Box out of bounds {obj.class_name} {obj.bbox_xyxy} vs image {w}x{h}",
                        object_id=obj.id
                    ))

            # tiny
            if self.check_tiny:
                if bw < self.min_box_size or bh < self.min_box_size:
                    issues.append(ValidationIssue(
                        type="tiny",
                        severity="info",
                        message=f"Tiny box {obj.class_name} {bw:.0f}x{bh:.0f} < {self.min_box_size}px",
                        object_id=obj.id,
                        details={"w": bw, "h": bh}
                    ))

            # low conf for AI
            if obj.is_ai and obj.confidence < self.min_conf:
                issues.append(ValidationIssue(
                    type="low_conf",
                    severity="info",
                    message=f"Low confidence AI box {obj.class_name} {obj.confidence:.2f} < {self.min_conf}",
                    object_id=obj.id
                ))

        # duplicate / heavy overlap check O(n^2) but okay for <~100 boxes
        if self.check_duplicate:
            for i in range(len(objs)):
                for j in range(i+1, len(objs)):
                    a = objs[i]; b = objs[j]
                    if not a.visible or not b.visible:
                        continue
                    iou = AnnotationObject.iou(a,b)
                    if iou > self.max_overlap_iou:
                        # if same class -> duplicate, else overlap warning
                        if a.class_id == b.class_id:
                            issues.append(ValidationIssue(
                                type="duplicate",
                                severity="warning",
                                message=f"Duplicate boxes {a.class_name} IoU={iou:.2f} [{a.bbox_xyxy}] vs [{b.bbox_xyxy}]",
                                object_id=a.id,
                                details={"iou": iou, "other_id": b.id}
                            ))
                        else:
                            issues.append(ValidationIssue(
                                type="overlap",
                                severity="info",
                                message=f"Heavy overlap different classes {a.class_name} vs {b.class_name} IoU={iou:.2f}",
                                object_id=a.id,
                                details={"iou": iou, "other_id": b.id}
                            ))

        return issues

    def validate_dataset(self, image_annotations: List[ImageAnnotations], class_names: List[str]) -> Dict[str, Any]:
        """
        Dataset level validation
        """
        from collections import Counter, defaultdict
        total_images = len(image_annotations)
        total_objects = sum(len(ann.objects) for ann in image_annotations)
        class_counter = Counter()
        size_stats = defaultdict(list)  # class -> list of areas
        issues_all: List[ValidationIssue] = []

        for ann in image_annotations:
            class_counter.update([o.class_name for o in ann.objects if o.visible])
            for o in ann.objects:
                if o.visible:
                    size_stats[o.class_name].append(o.area)
            issues_all.extend(self.validate_image(ann))

        # class imbalance
        imbalance = {}
        if class_counter:
            avg = sum(class_counter.values())/len(class_counter)
            for cname, cnt in class_counter.items():
                if cnt < avg * 0.1:
                    imbalance[cname] = f"Low sample {cnt} vs avg {avg:.1f}"

        # per class size
        size_summary = {}
        for cname, areas in size_stats.items():
            if areas:
                size_summary[cname] = {
                    "count": len(areas),
                    "min_area": min(areas),
                    "max_area": max(areas),
                    "avg_area": sum(areas)/len(areas)
                }

        return {
            "total_images": total_images,
            "total_objects": total_objects,
            "class_distribution": dict(class_counter),
            "size_summary": size_summary,
            "imbalance_warnings": imbalance,
            "total_issues": len(issues_all),
            "issues": [i.to_dict() for i in issues_all[:200]],  # limit
        }
