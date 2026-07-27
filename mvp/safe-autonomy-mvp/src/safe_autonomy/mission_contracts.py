from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from typing import Any
from uuid import uuid4


GridCell = tuple[int, int]


class MapFormat(StrEnum):
    GEOJSON = "GEOJSON"
    PGM = "PGM"
    GEOTIFF = "GEOTIFF"
    FIXTURE = "FIXTURE"


class CoordinateSystem(StrEnum):
    LOCAL_ENU = "LOCAL_ENU"
    WGS84_PROJECTED = "WGS84_PROJECTED"


class MapStatus(StrEnum):
    VALID = "VALID"
    DEGRADED = "DEGRADED"
    INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class MissionMap:
    map_id: str
    source_name: str
    source_format: MapFormat
    source_sha256: str
    source_size_bytes: int
    coordinate_system: CoordinateSystem
    width_cells: int
    height_cells: int
    resolution_m: float
    origin_x_m: float
    origin_y_m: float
    occupancy: bytes
    risk: tuple[float, ...]
    elevation_m: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        count = self.width_cells * self.height_cells
        if not self.map_id or self.width_cells <= 0 or self.height_cells <= 0 or self.resolution_m <= 0:
            raise ValueError("invalid mission map identity or dimensions")
        if len(self.occupancy) != count or len(self.risk) != count:
            raise ValueError("map layer sizes do not match dimensions")
        if self.elevation_m is not None and len(self.elevation_m) != count:
            raise ValueError("elevation layer size does not match dimensions")
        if any(value not in (0, 1, 2) for value in self.occupancy):
            raise ValueError("occupancy values must be free=0, occupied=1 or unknown=2")
        if any(not isfinite(value) or not 0.0 <= value <= 1.0 for value in self.risk):
            raise ValueError("risk values must be finite and in [0, 1]")

    def index(self, cell: GridCell) -> int:
        x, y = cell
        if not self.contains(cell):
            raise IndexError(cell)
        return y * self.width_cells + x

    def contains(self, cell: GridCell) -> bool:
        return 0 <= cell[0] < self.width_cells and 0 <= cell[1] < self.height_cells

    def occupancy_at(self, cell: GridCell) -> int:
        return self.occupancy[self.index(cell)]

    def risk_at(self, cell: GridCell) -> float:
        return self.risk[self.index(cell)]

    def elevation_at(self, cell: GridCell) -> float | None:
        return None if self.elevation_m is None else self.elevation_m[self.index(cell)]

    def to_cell(self, x_m: float, y_m: float) -> GridCell:
        return (
            round((x_m - self.origin_x_m) / self.resolution_m),
            round((y_m - self.origin_y_m) / self.resolution_m),
        )

    def to_point(self, cell: GridCell) -> tuple[float, float]:
        return (
            self.origin_x_m + cell[0] * self.resolution_m,
            self.origin_y_m + cell[1] * self.resolution_m,
        )


@dataclass(frozen=True, slots=True)
class MapAnalysis:
    occupied_cells: int
    free_cells: int
    unknown_cells: int
    obstacle_density: float
    free_space_components: int
    largest_free_component_cells: int
    minimum_elevation_m: float | None
    maximum_elevation_m: float | None
    status: MapStatus
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RoutePolicy:
    obstacle_inflation_m: float = 2.0
    minimum_terrain_clearance_m: float = 20.0
    maximum_climb_rate_mps: float = 4.0
    maximum_descent_rate_mps: float = 3.0
    cruise_speed_mps: float = 12.0
    risk_weight: float = 4.0
    elevation_weight: float = 0.05
    turn_penalty: float = 0.20
    unknown_is_blocked: bool = True
    requested_alternatives: int = 3
    minimum_distinctness: float = 0.20

    def __post_init__(self) -> None:
        positive = (
            self.minimum_terrain_clearance_m, self.maximum_climb_rate_mps,
            self.maximum_descent_rate_mps, self.cruise_speed_mps,
        )
        if any(value <= 0 for value in positive) or self.obstacle_inflation_m < 0:
            raise ValueError("invalid route policy")
        if not 1 <= self.requested_alternatives <= 5:
            raise ValueError("requested_alternatives must be in [1, 5]")


@dataclass(frozen=True, slots=True)
class RouteRequest:
    map_id: str
    start_x_m: float
    start_y_m: float
    goal_x_m: float
    goal_y_m: float
    start_altitude_m: float
    cruise_altitude_m: float
    policy: RoutePolicy = field(default_factory=RoutePolicy)
    request_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True, slots=True)
class RoutePoint3D:
    cell_x: int
    cell_y: int
    x_m: float
    y_m: float
    altitude_m: float
    time_from_start_s: float
    cumulative_cost: float


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    request_id: str
    rank_no: int
    total_cost: float
    length_m: float
    estimated_duration_s: float
    mean_risk: float
    minimum_clearance_m: float | None
    distinctness: float
    points: tuple[RoutePoint3D, ...]
    validation_reasons: tuple[str, ...] = ()
    candidate_id: str = field(default_factory=lambda: str(uuid4()))

    @property
    def valid(self) -> bool:
        return not self.validation_reasons


class FlightPhase(StrEnum):
    PREFLIGHT = "PREFLIGHT"
    TAKEOFF = "TAKEOFF"
    CLIMB = "CLIMB"
    CRUISE = "CRUISE"
    HOLD = "HOLD"
    RETURN = "RETURN"
    APPROACH = "APPROACH"
    LANDING = "LANDING"
    LANDED = "LANDED"
    EMERGENCY = "EMERGENCY"


class FindingSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SafeRecommendation(StrEnum):
    CONTINUE = "CONTINUE"
    REQUEST_SENSOR_UPDATE = "REQUEST_SENSOR_UPDATE"
    REQUEST_REPLAN = "REQUEST_REPLAN"
    HOLD = "HOLD"
    RETURN = "RETURN"
    LAND = "LAND"
    ABORT = "ABORT"


@dataclass(frozen=True, slots=True)
class FlightSample:
    timestamp_ms: int
    host_monotonic_ms: int
    armed: bool
    landed: bool
    reported_mode: str
    local_x_m: float
    local_y_m: float
    altitude_agl_m: float
    terrain_clearance_m: float | None
    ground_speed_mps: float
    vertical_speed_mps: float
    roll_deg: float
    pitch_deg: float
    battery_percent: float
    gps_quality: float
    estimator_healthy: bool
    link_quality: float
    telemetry_age_ms: int
    route_deviation_m: float
    distance_to_goal_m: float
    geofence_margin_m: float
    obstacle_ttc_s: float | None
    camera_healthy: bool
    tracker_healthy: bool
    landing_zone_clear: bool
    phase_elapsed_s: float = 0.0
    map_age_ms: int = 0
    telemetry_frame_id: str | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.battery_percent <= 100 or not 0 <= self.gps_quality <= 1 or not 0 <= self.link_quality <= 1:
            raise ValueError("invalid flight sample percentage/quality")
        if self.timestamp_ms < 0 or self.host_monotonic_ms < 0 or self.telemetry_age_ms < 0:
            raise ValueError("flight timestamps/age must be non-negative")
        numeric = (
            self.local_x_m, self.local_y_m, self.altitude_agl_m,
            self.ground_speed_mps, self.vertical_speed_mps, self.roll_deg,
            self.pitch_deg, self.battery_percent, self.gps_quality,
            self.link_quality, self.route_deviation_m, self.distance_to_goal_m,
            self.geofence_margin_m, self.phase_elapsed_s,
        )
        optional = (self.terrain_clearance_m, self.obstacle_ttc_s)
        if not all(isfinite(value) for value in numeric) or not all(value is None or isfinite(value) for value in optional):
            raise ValueError("flight sample values must be finite")


@dataclass(frozen=True, slots=True)
class FlightFinding:
    code: str
    severity: FindingSeverity
    message: str
    observed: dict[str, Any]
    limit: dict[str, Any]


@dataclass(frozen=True, slots=True)
class FlightAssessment:
    sample: FlightSample
    inferred_phase: FlightPhase
    previous_phase: FlightPhase | None
    transition_valid: bool
    health_score: float
    highest_severity: FindingSeverity
    recommendation: SafeRecommendation
    findings: tuple[FlightFinding, ...]
    created_at_ms: int
    assessment_id: str = field(default_factory=lambda: str(uuid4()))
    schema_version: str = "1.0"


@dataclass(frozen=True, slots=True)
class ScenarioDefinition:
    scenario_id: str
    version: str
    title: str
    category: str
    description: str
    overrides: dict[str, Any]
    expected_recommendation: SafeRecommendation
    minimum_severity: FindingSeverity
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    definition: ScenarioDefinition
    assessment: FlightAssessment
    passed: bool
    failure_reason: str | None
    started_at_ms: int
    completed_at_ms: int
    run_id: str = field(default_factory=lambda: str(uuid4()))
