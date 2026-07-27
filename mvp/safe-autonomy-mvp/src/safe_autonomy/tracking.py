from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .vision_contracts import TrackedObject


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class DetectionCandidate:
    class_id: int
    class_name: str
    confidence: float
    bbox_xyxy_px: tuple[float, float, float, float]


def intersection_over_union(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    ax1, ay1, ax2, ay2 = first
    bx1, by1, bx2, by2 = second
    ix1, iy1, ix2, iy2 = max(ax1, bx1), max(ay1, by1), min(ax2, bx2), min(ay2, by2)
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if intersection == 0:
        return 0.0
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - intersection
    return intersection / union if union > 0 else 0.0


@dataclass(slots=True)
class _TrackState:
    track_id: int
    class_id: int
    bbox: tuple[float, float, float, float]
    last_sequence: int


class IoUTracker:
    """Small deterministic tracker used for tests/fallback, not the production tracker."""

    name = "iou-fallback"

    def __init__(self, minimum_iou: float = 0.30, max_age_frames: int = 5) -> None:
        if not 0.0 < minimum_iou <= 1.0 or max_age_frames < 1:
            raise ValueError("invalid tracker policy")
        self.minimum_iou = minimum_iou
        self.max_age_frames = max_age_frames
        self._tracks: dict[int, _TrackState] = {}
        self._next_id = 1

    def update(self, detections: tuple[DetectionCandidate, ...], sequence_no: int) -> tuple[TrackedObject, ...]:
        self._tracks = {
            track_id: state
            for track_id, state in self._tracks.items()
            if sequence_no - state.last_sequence <= self.max_age_frames
        }
        unused_tracks = set(self._tracks)
        result: list[TrackedObject] = []
        for detection in sorted(detections, key=lambda item: (-item.confidence, item.class_id, item.bbox_xyxy_px)):
            candidates = [
                (intersection_over_union(detection.bbox_xyxy_px, self._tracks[track_id].bbox), track_id)
                for track_id in unused_tracks
                if self._tracks[track_id].class_id == detection.class_id
            ]
            best_iou, track_id = max(candidates, default=(0.0, -1))
            if best_iou < self.minimum_iou:
                track_id = self._next_id
                self._next_id += 1
            else:
                unused_tracks.remove(track_id)
            self._tracks[track_id] = _TrackState(track_id, detection.class_id, detection.bbox_xyxy_px, sequence_no)
            result.append(TrackedObject(
                object_id=str(uuid4()),
                track_id=track_id,
                class_id=detection.class_id,
                class_name=detection.class_name,
                confidence=detection.confidence,
                bbox_xyxy_px=detection.bbox_xyxy_px,
                tracker_backend=self.name,
            ))
        return tuple(result)


class UltralyticsByteTrackBackend:
    """YOLO detector + persistent ByteTrack IDs on in-memory frames."""

    name = "ultralytics-bytetrack"

    def __init__(
        self,
        model_path: str | Path,
        confidence: float = 0.25,
        allowed_classes: set[str] | None = None,
        tracker_config: str = "bytetrack.yaml",
    ) -> None:
        path = Path(model_path)
        if not path.is_file():
            raise ValueError("model_path must be an existing local file")
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("Install the perception extra: pip install -e '.[perception]'") from exc
        if not 0.0 < confidence <= 1.0:
            raise ValueError("confidence must be in (0, 1]")
        self._model = YOLO(str(path))
        self.confidence = confidence
        self.allowed_classes = allowed_classes
        self.tracker_config = tracker_config
        digest = _sha256_file(path)
        self.model_version = f"{path.name}:{digest[:12]}"

    def track(self, image) -> tuple[TrackedObject, ...]:
        results = self._model.track(
            source=image,
            persist=True,
            tracker=self.tracker_config,
            conf=self.confidence,
            verbose=False,
        )
        objects: list[TrackedObject] = []
        for result in results:
            names = result.names
            for index, box in enumerate(result.boxes):
                class_id = int(box.cls[0].item())
                class_name = str(names[class_id])
                if self.allowed_classes and class_name not in self.allowed_classes:
                    continue
                track_id = int(box.id[0].item()) if box.id is not None else None
                bbox = tuple(float(value) for value in box.xyxy[0].tolist())
                objects.append(TrackedObject(
                    object_id=str(uuid4()),
                    track_id=track_id,
                    class_id=class_id,
                    class_name=class_name,
                    confidence=float(box.conf[0].item()),
                    bbox_xyxy_px=bbox,
                    tracker_backend=self.name,
                ))
        return tuple(objects)


class OverlayRenderer:
    def __init__(self, trail_length: int = 30) -> None:
        if trail_length < 1:
            raise ValueError("trail_length must be positive")
        self.trail_length = trail_length
        self._trails: dict[int, list[tuple[int, int]]] = {}

    @staticmethod
    def _color(track_id: int | None) -> tuple[int, int, int]:
        seed = 0 if track_id is None else track_id
        return (64 + seed * 37 % 191, 64 + seed * 71 % 191, 64 + seed * 113 % 191)

    def render(self, image, objects: tuple[TrackedObject, ...], latency_ms: float, dropped: int):
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("OpenCV is required for the tracking overlay") from exc
        output = image.copy()
        for obj in objects:
            x1, y1, x2, y2 = (int(round(value)) for value in obj.bbox_xyxy_px)
            color = self._color(obj.track_id)
            cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
            label = f"{obj.class_name} #{obj.track_id if obj.track_id is not None else '-'} {obj.confidence:.2f}"
            cv2.putText(output, label, (x1, max(18, y1 - 7)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
            if obj.track_id is not None:
                trail = self._trails.setdefault(obj.track_id, [])
                trail.append(((x1 + x2) // 2, (y1 + y2) // 2))
                del trail[:-self.trail_length]
                for start, end in zip(trail, trail[1:]):
                    cv2.line(output, start, end, color, 2)
        cv2.putText(
            output, f"objects={len(objects)} latency={latency_ms:.1f}ms dropped={dropped}",
            (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2,
        )
        return output
