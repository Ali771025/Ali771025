from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from typing import Any
from uuid import uuid4


class SyncStatus(StrEnum):
    MATCHED = "MATCHED"
    TOO_OLD = "TOO_OLD"
    MISSING = "MISSING"


class HealthStatus(StrEnum):
    STARTING = "STARTING"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


@dataclass(frozen=True, slots=True)
class FrameMetadata:
    stream_id: str
    sequence_no: int
    host_monotonic_ms: int
    captured_at_ms: int
    width_px: int
    height_px: int
    pts_ns: int | None = None
    dts_ns: int | None = None
    duration_ns: int | None = None
    pixel_format: str = "BGR"
    vision_frame_id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if not self.stream_id or self.sequence_no < 0:
            raise ValueError("stream_id and non-negative sequence_no are required")
        if self.host_monotonic_ms < 0 or self.captured_at_ms < 0:
            raise ValueError("timestamps must be non-negative")
        if self.width_px <= 0 or self.height_px <= 0:
            raise ValueError("frame dimensions must be positive")


@dataclass(frozen=True, slots=True)
class CapturedFrame:
    metadata: FrameMetadata
    image: Any
    capture_latency_ms: float = 0.0
    dropped_before: int = 0


@dataclass(frozen=True, slots=True)
class TrackedObject:
    object_id: str
    track_id: int | None
    class_id: int
    class_name: str
    confidence: float
    bbox_xyxy_px: tuple[float, float, float, float]
    tracker_backend: str

    def __post_init__(self) -> None:
        if not self.object_id or not self.class_name:
            raise ValueError("object identity is required")
        if not isfinite(self.confidence) or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be finite and in [0, 1]")
        x1, y1, x2, y2 = self.bbox_xyxy_px
        if min(x1, y1) < 0 or x2 <= x1 or y2 <= y1:
            raise ValueError("invalid bounding box")


@dataclass(frozen=True, slots=True)
class ProcessedFrame:
    captured: CapturedFrame
    objects: tuple[TrackedObject, ...]
    inference_latency_ms: float
    publish_latency_ms: float
    end_to_end_latency_ms: float
    annotated_image: Any = None


@dataclass(frozen=True, slots=True)
class SyncRecord:
    vision_frame_id: str
    telemetry_frame_id: str | None
    skew_ms: int | None
    status: SyncStatus
    created_at_ms: int
    policy_version: str = "monotonic-nearest-v1"
    sync_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True, slots=True)
class ModuleHealth:
    module_id: str
    status: HealthStatus
    host_monotonic_ms: int
    latency_ms: float = 0.0
    queue_depth: int = 0
    dropped_count: int = 0
    details: dict[str, object] = field(default_factory=dict)
    created_at_ms: int = 0
    event_id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if not self.module_id or self.host_monotonic_ms < 0:
            raise ValueError("module_id and monotonic timestamp are required")
        if self.latency_ms < 0 or self.queue_depth < 0 or self.dropped_count < 0:
            raise ValueError("health metrics cannot be negative")
