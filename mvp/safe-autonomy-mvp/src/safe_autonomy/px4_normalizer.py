from __future__ import annotations

from collections import defaultdict
from typing import Any

from .sensor_contracts import (
    AirspeedSample,
    BarometerSample,
    BatterySample,
    GpsSample,
    ImuSample,
    MagnetometerSample,
    RangefinderSample,
    SensorHeader,
    SensorKind,
)


def _value(message: Any, name: str, default: Any = None) -> Any:
    value = getattr(message, name, default)
    if value is None:
        raise ValueError(f"PX4 message field is missing: {name}")
    return value


class Px4MessageNormalizer:
    """Version boundary between px4_msgs objects and internal typed contracts."""

    def __init__(self) -> None:
        self._sequence: dict[SensorKind, int] = defaultdict(int)

    def _header(self, kind: SensorKind, timestamp_us: int, source: str, frame_id: str, quality: float, calibration: str | None = None) -> SensorHeader:
        self._sequence[kind] += 1
        return SensorHeader(
            timestamp_ms=int(timestamp_us) // 1_000,
            sequence_no=self._sequence[kind], source=source, frame_id=frame_id,
            quality=max(0.0, min(1.0, quality)), calibration_version=calibration,
        )

    def gps(self, message: Any) -> GpsSample:
        fix_type = int(_value(message, "fix_type", 0))
        eph = float(_value(message, "eph", 99.0))
        epv = float(_value(message, "epv", 99.0))
        quality = (0.95 if fix_type >= 3 else 0.30) * (1.0 if eph <= 2.0 else 0.6)
        return GpsSample(
            self._header(SensorKind.GPS, _value(message, "timestamp"), "px4-gps", "wgs84", quality),
            float(_value(message, "lat")) / 10_000_000.0,
            float(_value(message, "lon")) / 10_000_000.0,
            float(_value(message, "alt")) / 1_000.0,
            float(_value(message, "vel_n_m_s", 0.0)),
            float(_value(message, "vel_e_m_s", 0.0)),
            float(_value(message, "vel_d_m_s", 0.0)),
            eph, epv, fix_type,
        )

    def imu(self, message: Any) -> ImuSample:
        clipping = sum(int(value) for value in _value(message, "accelerometer_clipping", [0, 0, 0]))
        quality = 1.0 if clipping == 0 else 0.4
        return ImuSample(
            self._header(SensorKind.IMU, _value(message, "timestamp"), "px4-imu", "base_link", quality),
            tuple(float(value) for value in _value(message, "accelerometer_m_s2")),
            tuple(float(value) for value in _value(message, "gyro_rad")),
        )

    def barometer(self, message: Any) -> BarometerSample:
        return BarometerSample(
            self._header(SensorKind.BAROMETER, _value(message, "timestamp"), "px4-baro", "base_link", 0.90),
            float(_value(message, "baro_pressure_pa")),
            float(_value(message, "baro_alt_meter")), 1.0,
        )

    def magnetometer(self, message: Any) -> MagnetometerSample:
        gauss = _value(message, "magnetometer_ga")
        return MagnetometerSample(
            self._header(SensorKind.MAGNETOMETER, _value(message, "timestamp"), "px4-mag", "base_link", 0.90),
            tuple(float(value) * 100.0 for value in gauss),
        )

    def airspeed(self, message: Any) -> AirspeedSample:
        indicated = float(_value(message, "indicated_airspeed_m_s", _value(message, "calibrated_airspeed_m_s", 0.0)))
        true = float(_value(message, "true_airspeed_m_s", indicated))
        return AirspeedSample(
            self._header(SensorKind.AIRSPEED, _value(message, "timestamp"), "px4-airspeed", "base_link", 0.90),
            indicated, true,
        )

    def rangefinder(self, message: Any) -> RangefinderSample:
        return RangefinderSample(
            self._header(SensorKind.RANGEFINDER, _value(message, "timestamp"), "px4-rangefinder", "base_link", 0.90),
            float(_value(message, "current_distance")),
            max(float(_value(message, "variance", 0.01)), 0.0),
            float(_value(message, "min_distance")),
            float(_value(message, "max_distance")),
        )

    def battery(self, message: Any) -> BatterySample:
        remaining = float(_value(message, "remaining", 0.0))
        percent = remaining * 100.0 if remaining <= 1.0 else remaining
        return BatterySample(
            self._header(SensorKind.BATTERY, _value(message, "timestamp"), "px4-battery", "base_link", 0.95),
            percent,
            float(_value(message, "voltage_v", 0.0)),
            float(_value(message, "current_a", 0.0)),
            float(_value(message, "temperature", 0.0)),
        )

