from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from typing import Any
from uuid import uuid4


class GateStatus(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class ReadinessState(StrEnum):
    READY = "READY"
    DEGRADED = "DEGRADED"
    NOT_READY = "NOT_READY"


class TemporalVerdict(StrEnum):
    ACCEPT = "ACCEPT"
    DEGRADED = "DEGRADED"
    REJECT = "REJECT"


@dataclass(frozen=True, slots=True)
class GateResult:
    gate: str
    status: GateStatus
    reason: str
    observed: dict[str, Any]
    limit: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TemporalObservation:
    source: str
    sequence: int
    source_monotonic_ms: int
    received_monotonic_ms: int
    verdict: TemporalVerdict
    age_ms: int
    cross_source_skew_ms: int | None
    reasons: tuple[str, ...]
    observation_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True, slots=True)
class ModuleHeartbeat:
    module_id: str
    observed_monotonic_ms: int
    status: str
    latency_ms: float
    queue_depth: int = 0
    dropped_messages: int = 0
    detail: str = ""

    def __post_init__(self) -> None:
        if not self.module_id or self.observed_monotonic_ms < 0:
            raise ValueError("invalid heartbeat identity/timestamp")
        if not isfinite(self.latency_ms) or self.latency_ms < 0:
            raise ValueError("latency_ms must be finite and non-negative")
        if self.queue_depth < 0 or self.dropped_messages < 0:
            raise ValueError("queue/drop counters must be non-negative")


@dataclass(frozen=True, slots=True)
class SystemReadiness:
    state: ReadinessState
    score: float
    gates: tuple[GateResult, ...]
    evaluated_monotonic_ms: int
    snapshot_id: str = field(default_factory=lambda: str(uuid4()))
    schema_version: str = "2.0"


@dataclass(frozen=True, slots=True)
class DynamicTrack:
    track_id: str
    x_m: float
    y_m: float
    velocity_x_mps: float
    velocity_y_mps: float
    radius_m: float
    confidence: float
    observed_monotonic_ms: int

    def __post_init__(self) -> None:
        values = (self.x_m, self.y_m, self.velocity_x_mps, self.velocity_y_mps, self.radius_m, self.confidence)
        if not self.track_id or not all(isfinite(value) for value in values):
            raise ValueError("invalid dynamic track")
        if self.radius_m <= 0 or not 0 <= self.confidence <= 1 or self.observed_monotonic_ms < 0:
            raise ValueError("invalid dynamic track bounds")


@dataclass(frozen=True, slots=True)
class EnergyAssessment:
    feasible: bool
    estimated_energy_wh: float
    available_energy_wh: float
    reserve_energy_wh: float
    margin_wh: float
    wind_penalty_ratio: float
    gates: tuple[GateResult, ...]
    assessment_id: str = field(default_factory=lambda: str(uuid4()))
    schema_version: str = "2.0"


@dataclass(frozen=True, slots=True)
class RouteRevalidation:
    route_candidate_id: str
    recommendation: str
    cross_track_error_m: float
    progress_ratio: float
    remaining_distance_m: float
    corridor_risk: float
    reasons: tuple[str, ...]
    evaluated_monotonic_ms: int
    assessment_id: str = field(default_factory=lambda: str(uuid4()))
    schema_version: str = "2.0"


@dataclass(frozen=True, slots=True)
class AssuranceReport:
    mission_id: str
    overall_status: GateStatus
    readiness: SystemReadiness
    energy: EnergyAssessment
    gates: tuple[GateResult, ...]
    input_sha256: str
    created_at_ms: int
    report_id: str = field(default_factory=lambda: str(uuid4()))
    schema_version: str = "2.0"
