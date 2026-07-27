from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Protocol
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    source_name: str
    sha256: str
    size_bytes: int
    duration_ms: int
    width_px: int
    height_px: int
    fps: float
    codec: str


@dataclass(frozen=True, slots=True)
class SampledFrame:
    frame_index: int
    video_timestamp_ms: int
    path: Path


@dataclass(frozen=True, slots=True)
class Detection2D:
    detection_id: str
    frame_index: int
    video_timestamp_ms: int
    class_id: int
    class_name: str
    confidence: float
    x1_px: float
    y1_px: float
    x2_px: float
    y2_px: float
    model_version: str
    track_id: str | None = None
    depth_m: float | None = None
    depth_variance_m2: float | None = None
    calibration_version: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if self.x1_px < 0 or self.y1_px < 0 or self.x2_px <= self.x1_px or self.y2_px <= self.y1_px:
            raise ValueError("invalid bounding box")
        if self.depth_m is not None and self.depth_m <= 0:
            raise ValueError("depth_m must be positive")


class DetectorBackend(Protocol):
    name: str
    model_version: str
    configuration: dict[str, object]

    def predict(self, frame: SampledFrame) -> tuple[Detection2D, ...]: ...


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe_video(path: str | Path) -> VideoMetadata:
    source = Path(path)
    command = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "format=duration,size:stream=codec_name,width,height,avg_frame_rate",
        "-of", "json", str(source),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    stream = payload["streams"][0]
    format_info = payload["format"]
    return VideoMetadata(
        source_name=source.name,
        sha256=_sha256_file(source),
        size_bytes=int(format_info["size"]),
        duration_ms=round(float(format_info["duration"]) * 1000),
        width_px=int(stream["width"]),
        height_px=int(stream["height"]),
        fps=float(Fraction(stream["avg_frame_rate"])),
        codec=str(stream["codec_name"]),
    )


def sample_frames(path: str | Path, output_dir: str | Path, sample_fps: float, source_fps: float) -> tuple[SampledFrame, ...]:
    if sample_fps <= 0:
        raise ValueError("sample_fps must be positive")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    pattern = output / "frame_%06d.jpg"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(path), "-vf", f"fps={sample_fps}", str(pattern)],
        check=True,
    )
    interval_ms = round(1000.0 / sample_fps)
    return tuple(
        SampledFrame(round(index * source_fps / sample_fps), index * interval_ms, frame_path)
        for index, frame_path in enumerate(sorted(output.glob("frame_*.jpg")))
    )


class MetadataOnlyBackend:
    name = "metadata-only"
    model_version = "none"
    configuration: dict[str, object] = {"mode": "metadata-only"}

    def predict(self, frame: SampledFrame) -> tuple[Detection2D, ...]:
        return ()


class UltralyticsBackend:
    name = "ultralytics"

    def __init__(self, model_path: str, confidence: float = 0.25, allowed_classes: set[str] | None = None) -> None:
        model_file = Path(model_path)
        if not model_file.is_file():
            raise ValueError("model_path must be an existing local file")
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("Install the perception extra: pip install -e '.[perception]'") from exc
        self._model = YOLO(str(model_file))
        self.model_version = model_file.name
        self.confidence = confidence
        self.allowed_classes = allowed_classes
        model_digest = _sha256_file(model_file)
        self.configuration = {
            "model_sha256": model_digest,
            "confidence": confidence,
            "allowed_classes": sorted(allowed_classes) if allowed_classes else [],
        }

    def predict(self, frame: SampledFrame) -> tuple[Detection2D, ...]:
        results = self._model.predict(source=str(frame.path), conf=self.confidence, verbose=False)
        detections: list[Detection2D] = []
        for result in results:
            names = result.names
            for box in result.boxes:
                class_id = int(box.cls[0].item())
                class_name = str(names[class_id])
                if self.allowed_classes and class_name not in self.allowed_classes:
                    continue
                x1, y1, x2, y2 = (float(value) for value in box.xyxy[0].tolist())
                detections.append(Detection2D(
                    detection_id=str(uuid4()),
                    frame_index=frame.frame_index,
                    video_timestamp_ms=frame.video_timestamp_ms,
                    class_id=class_id,
                    class_name=class_name,
                    confidence=float(box.conf[0].item()),
                    x1_px=x1, y1_px=y1, x2_px=x2, y2_px=y2,
                    model_version=self.model_version,
                ))
        return tuple(detections)
