from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from typing import Any


SCHEMA_VERSION = "1.0"


class MissionState(StrEnum):
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    READY = "READY"
    EXECUTING = "EXECUTING"
    HOLD = "HOLD"
    RETURN = "RETURN"
    LAND = "LAND"
    ABORTED = "ABORTED"


class Intent(StrEnum):
    START_MISSION = "START_MISSION"
    REQUEST_REROUTE = "REQUEST_REROUTE"
    HOLD = "HOLD"
    RETURN = "RETURN"
    LAND = "LAND"
    ABORT_MISSION = "ABORT_MISSION"
    ABSTAIN = "ABSTAIN"


class Verdict(StrEnum):
    PASS = "PASS"
    REJECT = "REJECT"


def _bounded(name: str, value: float, low: float, high: float) -> None:
    if not isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be finite and in [{low}, {high}]")


@dataclass(frozen=True, slots=True)
class Vector2:
    x_m: float
    y_m: float

    def __post_init__(self) -> None:
        if not isfinite(self.x_m) or not isfinite(self.y_m):
            raise ValueError("Vector2 coordinates must be finite")


@dataclass(frozen=True, slots=True)
class Pose2D:
    position: Vector2
    heading_rad: float
    timestamp_ms: int
    quality: float
    covariance_m2: float = 0.0
    frame_id: str = "map"

    def __post_init__(self) -> None:
        if self.timestamp_ms < 0:
            raise ValueError("timestamp_ms must be non-negative")
        _bounded("quality", self.quality, 0.0, 1.0)
        if self.covariance_m2 < 0 or not isfinite(self.covariance_m2):
            raise ValueError("covariance_m2 must be finite and non-negative")
        if not self.frame_id:
            raise ValueError("frame_id is required")


@dataclass(frozen=True, slots=True)
class Obstacle:
    obstacle_id: str
    position: Vector2
    radius_m: float
    confidence: float
    timestamp_ms: int
    position_variance_m2: float = 0.0

    def __post_init__(self) -> None:
        if not self.obstacle_id:
            raise ValueError("obstacle_id is required")
        if self.radius_m <= 0 or not isfinite(self.radius_m):
            raise ValueError("radius_m must be finite and positive")
        _bounded("confidence", self.confidence, 0.0, 1.0)
        if self.timestamp_ms < 0:
            raise ValueError("timestamp_ms must be non-negative")
        if self.position_variance_m2 < 0 or not isfinite(self.position_variance_m2):
            raise ValueError("position_variance_m2 must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class WorldSnapshot:
    snapshot_id: str
    created_at_ms: int
    pose: Pose2D
    obstacles: tuple[Obstacle, ...]
    battery_percent: float
    battery_timestamp_ms: int
    source_sequence: int
    stale_sources: tuple[str, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.snapshot_id:
            raise ValueError("snapshot_id is required")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if self.created_at_ms < self.pose.timestamp_ms:
            raise ValueError("snapshot cannot predate pose")
        if self.battery_timestamp_ms < 0 or self.created_at_ms < self.battery_timestamp_ms:
            raise ValueError("battery timestamp is invalid or in the future")
        _bounded("battery_percent", self.battery_percent, 0.0, 100.0)
        if self.source_sequence < 0:
            raise ValueError("source_sequence must be non-negative")


@dataclass(frozen=True, slots=True)
class TrajectoryPoint:
    position: Vector2
    time_from_start_s: float
    speed_mps: float

    def __post_init__(self) -> None:
        if self.time_from_start_s < 0 or not isfinite(self.time_from_start_s):
            raise ValueError("time_from_start_s must be finite and non-negative")
        if self.speed_mps < 0 or not isfinite(self.speed_mps):
            raise ValueError("speed_mps must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class Trajectory:
    trajectory_id: str
    request_id: str
    world_snapshot_id: str
    generated_at_ms: int
    points: tuple[TrajectoryPoint, ...]
    control_authority: str = "MISSION_MANAGER"
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.trajectory_id or not self.request_id or not self.world_snapshot_id:
            raise ValueError("trajectory identifiers are required")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version: {self.schema_version}")
        if len(self.points) < 2:
            raise ValueError("trajectory requires at least two points")
        times = tuple(point.time_from_start_s for point in self.points)
        if any(b <= a for a, b in zip(times, times[1:])):
            raise ValueError("trajectory time must be strictly increasing")


@dataclass(frozen=True, slots=True)
class GateResult:
    gate: str
    passed: bool
    reason: str
    observed: Any = None
    limit: Any = None


@dataclass(frozen=True, slots=True)
class SafetyDecision:
    request_id: str
    trajectory_id: str
    evaluated_at_ms: int
    verdict: Verdict
    gates: tuple[GateResult, ...]
    schema_version: str = SCHEMA_VERSION

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(g.reason for g in self.gates if not g.passed)


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_type: str
    timestamp_ms: int
    correlation_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION
