from __future__ import annotations

from dataclasses import dataclass
from math import cos, pi, sqrt
from uuid import uuid4

from .sensor_contracts import (
    AirspeedSample,
    BarometerSample,
    BatterySample,
    GpsSample,
    ImuSample,
    MagnetometerSample,
    PerceptionObject,
    RangefinderSample,
    SensorKind,
    SensorSample,
    TelemetryFrame,
)


@dataclass(frozen=True, slots=True)
class FusionPolicy:
    max_age_ms: dict[SensorKind, int]
    required_sources: tuple[SensorKind, ...] = (SensorKind.GPS, SensorKind.IMU, SensorKind.BATTERY)
    max_timestamp_skew_ms: int = 100
    minimum_quality: float = 0.60

    @classmethod
    def default(cls) -> "FusionPolicy":
        return cls({
            SensorKind.GPS: 500,
            SensorKind.IMU: 100,
            SensorKind.BAROMETER: 500,
            SensorKind.MAGNETOMETER: 250,
            SensorKind.AIRSPEED: 500,
            SensorKind.RANGEFINDER: 250,
            SensorKind.BATTERY: 1_000,
        })


class TelemetrySynchronizer:
    """Deterministic development fusion; raw IMU is never integrated as a flight estimator."""

    def __init__(self, home_latitude_deg: float, home_longitude_deg: float, home_altitude_m: float, policy: FusionPolicy | None = None) -> None:
        self.home_latitude_deg = home_latitude_deg
        self.home_longitude_deg = home_longitude_deg
        self.home_altitude_m = home_altitude_m
        self.policy = policy or FusionPolicy.default()
        self._latest: dict[SensorKind, SensorSample] = {}
        self._objects: tuple[PerceptionObject, ...] = ()

    def update(self, kind: SensorKind, sample: SensorSample) -> None:
        previous = self._latest.get(kind)
        if previous and sample.header.timestamp_ms < previous.header.timestamp_ms:
            raise ValueError(f"out-of-order {kind} sample")
        self._latest[kind] = sample

    def update_perception(self, objects: tuple[PerceptionObject, ...]) -> None:
        self._objects = tuple(sorted(objects, key=lambda item: item.object_id))

    def snapshot(self, now_ms: int, host_monotonic_ms: int | None = None) -> TelemetryFrame:
        missing = [kind.value for kind in self.policy.required_sources if kind not in self._latest]
        if missing:
            raise RuntimeError(f"missing required telemetry: {', '.join(missing)}")
        stale: list[str] = []
        for kind, sample in self._latest.items():
            age = now_ms - sample.header.timestamp_ms
            if age < 0:
                raise ValueError(f"future timestamp from {kind.value}")
            if age > self.policy.max_age_ms.get(kind, 500):
                stale.append(kind.value)
            if sample.header.quality < self.policy.minimum_quality:
                stale.append(f"{kind.value}_QUALITY")

        required_samples = [self._latest[kind] for kind in self.policy.required_sources]
        timestamps = [sample.header.timestamp_ms for sample in required_samples]
        skew_ms = max(timestamps) - min(timestamps)
        if skew_ms > self.policy.max_timestamp_skew_ms:
            stale.append("TIMESTAMP_SKEW")

        gps = self._require(GpsSample, SensorKind.GPS)
        imu = self._require(ImuSample, SensorKind.IMU)
        battery = self._require(BatterySample, SensorKind.BATTERY)
        local_x, local_y = self._gps_to_local(gps)
        altitude_m = self._fused_altitude(gps)
        qualities = [sample.header.quality for sample in required_samples]
        overall_quality = min(qualities) * (0.5 if stale else 1.0)
        fresh_objects = tuple(obj for obj in self._objects if 0 <= now_ms - obj.timestamp_ms <= 500)
        _ = imu  # Raw IMU health is checked; PX4 EKF owns attitude/state estimation in production.
        return TelemetryFrame(
            telemetry_frame_id=str(uuid4()),
            created_at_ms=now_ms,
            local_x_m=local_x,
            local_y_m=local_y,
            altitude_m=altitude_m,
            velocity_north_mps=gps.velocity_north_mps,
            velocity_east_mps=gps.velocity_east_mps,
            velocity_down_mps=gps.velocity_down_mps,
            battery_percent=battery.remaining_percent,
            overall_quality=max(0.0, min(1.0, overall_quality)),
            timestamp_skew_ms=skew_ms,
            stale_sources=tuple(sorted(set(stale))),
            source_sample_ids=tuple(sample.header.sample_id for sample in self._latest.values()),
            perception_objects=fresh_objects,
            host_monotonic_ms=host_monotonic_ms,
        )

    def samples(self) -> tuple[tuple[SensorKind, SensorSample], ...]:
        return tuple(sorted(self._latest.items(), key=lambda item: item[0].value))

    def _require(self, expected_type, kind: SensorKind):
        sample = self._latest[kind]
        if not isinstance(sample, expected_type):
            raise TypeError(f"{kind.value} sample has invalid type")
        return sample

    def _gps_to_local(self, gps: GpsSample) -> tuple[float, float]:
        earth_radius_m = 6_378_137.0
        latitude_rad = self.home_latitude_deg * pi / 180.0
        x = (gps.longitude_deg - self.home_longitude_deg) * pi / 180.0 * earth_radius_m * cos(latitude_rad)
        y = (gps.latitude_deg - self.home_latitude_deg) * pi / 180.0 * earth_radius_m
        return x, y

    def _fused_altitude(self, gps: GpsSample) -> float:
        barometer = self._latest.get(SensorKind.BAROMETER)
        gps_local_altitude = gps.altitude_msl_m - self.home_altitude_m
        if not isinstance(barometer, BarometerSample):
            return gps_local_altitude
        gps_variance = max(gps.vertical_accuracy_m ** 2, 0.01)
        baro_variance = max(barometer.variance_m2, 0.01)
        # PX4 `baro_alt_meter` is an MSL altitude; convert to local (AGL-home) before fusion.
        baro_local_altitude = barometer.altitude_m - self.home_altitude_m
        return (
            gps_local_altitude / gps_variance + baro_local_altitude / baro_variance
        ) / (1.0 / gps_variance + 1.0 / baro_variance)
