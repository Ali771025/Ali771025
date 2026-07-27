from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from typing import Any
from uuid import uuid4


class SensorKind(StrEnum):
    GPS = "GPS"
    IMU = "IMU"
    BAROMETER = "BAROMETER"
    MAGNETOMETER = "MAGNETOMETER"
    AIRSPEED = "AIRSPEED"
    RANGEFINDER = "RANGEFINDER"
    BATTERY = "BATTERY"
    PX4_ESTIMATOR = "PX4_ESTIMATOR"


@dataclass(frozen=True, slots=True)
class SensorHeader:
    timestamp_ms: int
    sequence_no: int
    source: str
    frame_id: str
    quality: float
    calibration_version: str | None = None
    sample_id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if self.timestamp_ms < 0 or self.sequence_no < 0:
            raise ValueError("timestamp and sequence must be non-negative")
        if not self.source or not self.frame_id or not self.sample_id:
            raise ValueError("source, frame_id and sample_id are required")
        if not isfinite(self.quality) or not 0.0 <= self.quality <= 1.0:
            raise ValueError("quality must be finite and in [0, 1]")


@dataclass(frozen=True, slots=True)
class GpsSample:
    header: SensorHeader
    latitude_deg: float
    longitude_deg: float
    altitude_msl_m: float
    velocity_north_mps: float
    velocity_east_mps: float
    velocity_down_mps: float
    horizontal_accuracy_m: float
    vertical_accuracy_m: float
    fix_type: int

    def __post_init__(self) -> None:
        if not -90.0 <= self.latitude_deg <= 90.0 or not -180.0 <= self.longitude_deg <= 180.0:
            raise ValueError("invalid GPS coordinates")
        if self.horizontal_accuracy_m < 0 or self.vertical_accuracy_m < 0:
            raise ValueError("GPS accuracy must be non-negative")
        if self.fix_type < 0:
            raise ValueError("fix_type must be non-negative")


@dataclass(frozen=True, slots=True)
class ImuSample:
    header: SensorHeader
    acceleration_mps2: tuple[float, float, float]
    angular_velocity_rps: tuple[float, float, float]
    temperature_c: float | None = None

    def __post_init__(self) -> None:
        values = (*self.acceleration_mps2, *self.angular_velocity_rps)
        if len(self.acceleration_mps2) != 3 or len(self.angular_velocity_rps) != 3:
            raise ValueError("IMU vectors must contain three axes")
        if not all(isfinite(value) for value in values):
            raise ValueError("IMU values must be finite")


@dataclass(frozen=True, slots=True)
class BarometerSample:
    header: SensorHeader
    pressure_pa: float
    altitude_m: float
    variance_m2: float

    def __post_init__(self) -> None:
        if self.pressure_pa <= 0 or self.variance_m2 < 0:
            raise ValueError("invalid barometer measurement")


@dataclass(frozen=True, slots=True)
class MagnetometerSample:
    header: SensorHeader
    magnetic_field_ut: tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class AirspeedSample:
    header: SensorHeader
    indicated_airspeed_mps: float
    true_airspeed_mps: float | None = None

    def __post_init__(self) -> None:
        if self.indicated_airspeed_mps < 0 or (self.true_airspeed_mps is not None and self.true_airspeed_mps < 0):
            raise ValueError("airspeed cannot be negative")


@dataclass(frozen=True, slots=True)
class RangefinderSample:
    header: SensorHeader
    distance_m: float
    variance_m2: float
    min_range_m: float
    max_range_m: float

    def __post_init__(self) -> None:
        if self.variance_m2 < 0 or not self.min_range_m <= self.distance_m <= self.max_range_m:
            raise ValueError("rangefinder measurement is outside its declared range")


@dataclass(frozen=True, slots=True)
class BatterySample:
    header: SensorHeader
    remaining_percent: float
    voltage_v: float
    current_a: float
    temperature_c: float | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.remaining_percent <= 100.0 or self.voltage_v < 0:
            raise ValueError("invalid battery measurement")


@dataclass(frozen=True, slots=True)
class PerceptionObject:
    object_id: str
    class_name: str
    confidence: float
    timestamp_ms: int
    bbox_xyxy_px: tuple[float, float, float, float]
    track_id: str | None = None
    depth_m: float | None = None
    depth_variance_m2: float | None = None
    relative_velocity_mps: float | None = None
    ttc_s: float | None = None

    def __post_init__(self) -> None:
        if not self.object_id or not self.class_name or not 0.0 <= self.confidence <= 1.0:
            raise ValueError("invalid perception object identity or confidence")
        x1, y1, x2, y2 = self.bbox_xyxy_px
        if min(x1, y1) < 0 or x2 <= x1 or y2 <= y1:
            raise ValueError("invalid perception bounding box")
        if self.depth_m is not None and self.depth_m <= 0:
            raise ValueError("depth must be positive")
        if self.ttc_s is not None and self.ttc_s < 0:
            raise ValueError("TTC cannot be negative")


SensorSample = GpsSample | ImuSample | BarometerSample | MagnetometerSample | AirspeedSample | RangefinderSample | BatterySample


@dataclass(frozen=True, slots=True)
class TelemetryFrame:
    telemetry_frame_id: str
    created_at_ms: int
    local_x_m: float
    local_y_m: float
    altitude_m: float
    velocity_north_mps: float
    velocity_east_mps: float
    velocity_down_mps: float
    battery_percent: float
    overall_quality: float
    timestamp_skew_ms: int
    stale_sources: tuple[str, ...]
    source_sample_ids: tuple[str, ...]
    perception_objects: tuple[PerceptionObject, ...] = ()
    schema_version: str = "1.0"
    host_monotonic_ms: int | None = None

    def __post_init__(self) -> None:
        numeric = (
            self.local_x_m, self.local_y_m, self.altitude_m,
            self.velocity_north_mps, self.velocity_east_mps,
            self.velocity_down_mps, self.battery_percent, self.overall_quality,
        )
        if not all(isfinite(value) for value in numeric):
            raise ValueError("telemetry frame values must be finite")
        if not 0.0 <= self.battery_percent <= 100.0 or not 0.0 <= self.overall_quality <= 1.0:
            raise ValueError("telemetry percentage/quality out of range")
        if self.host_monotonic_ms is not None and self.host_monotonic_ms < 0:
            raise ValueError("host_monotonic_ms must be non-negative")


def sensor_payload(sample: SensorSample) -> dict[str, Any]:
    from dataclasses import asdict

    payload = asdict(sample)
    payload.pop("header", None)
    return payload
