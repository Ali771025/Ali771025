from __future__ import annotations

import unittest

from safe_autonomy.advisory import AdvisoryIntent, DeterministicDecisionEngine
from safe_autonomy.sensor_contracts import (
    BarometerSample,
    BatterySample,
    GpsSample,
    ImuSample,
    PerceptionObject,
    SensorHeader,
    SensorKind,
)
from safe_autonomy.sensor_fusion import TelemetrySynchronizer


NOW = 50_000


def synchronizer(timestamp_ms: int = NOW, battery: float = 80.0) -> TelemetrySynchronizer:
    fusion = TelemetrySynchronizer(35.0, 51.0, 1_000.0)
    fusion.update(SensorKind.GPS, GpsSample(
        SensorHeader(timestamp_ms, 1, "gps", "wgs84", 0.95),
        35.0001, 51.0001, 1_020.0, 1.0, 2.0, 0.0, 1.0, 2.0, 3,
    ))
    fusion.update(SensorKind.IMU, ImuSample(
        SensorHeader(timestamp_ms, 1, "imu", "base_link", 0.98),
        (0.0, 0.0, 9.81), (0.0, 0.0, 0.0),
    ))
    fusion.update(SensorKind.BATTERY, BatterySample(
        SensorHeader(timestamp_ms, 1, "battery", "base_link", 0.99),
        battery, 15.0, 5.0,
    ))
    # baro_alt_meter is an MSL altitude (same frame as GPS).  With home=1000 m,
    # GPS reports 1020 m MSL (20 m local) with vertical variance ≈ 4 m^2, and
    # the barometer reports ~1020.5 m MSL with variance 0.25 m^2.  The weighted
    # fusion should yield ~20.47 m local altitude.
    fusion.update(SensorKind.BAROMETER, BarometerSample(
        SensorHeader(timestamp_ms, 1, "baro", "base_link", 0.90),
        90_000.0, 1020.5, 0.25,
    ))
    return fusion


class SensorFusionTests(unittest.TestCase):
    def test_fuses_complete_fresh_frame(self) -> None:
        frame = synchronizer().snapshot(NOW)
        self.assertFalse(frame.stale_sources)
        self.assertGreater(frame.local_x_m, 0)
        self.assertGreater(frame.local_y_m, 0)
        self.assertAlmostEqual(frame.altitude_m, 20.47, places=1)
        self.assertEqual(len(frame.source_sample_ids), 4)

    def test_stale_required_data_fails_closed_in_decision(self) -> None:
        frame = synchronizer(NOW - 1_000).snapshot(NOW)
        self.assertIn("GPS", frame.stale_sources)
        decision = DeterministicDecisionEngine().decide(frame)
        self.assertEqual(decision.intent, AdvisoryIntent.HOLD)

    def test_2d_detection_does_not_become_reroute(self) -> None:
        fusion = synchronizer()
        fusion.update_perception((PerceptionObject(
            "o1", "airplane", 0.9, NOW, (1.0, 1.0, 100.0, 100.0),
        ),))
        decision = DeterministicDecisionEngine().decide(fusion.snapshot(NOW))
        self.assertEqual(decision.intent, AdvisoryIntent.REQUEST_SENSOR_UPDATE)

    def test_calibrated_ttc_can_request_reroute(self) -> None:
        fusion = synchronizer()
        fusion.update_perception((PerceptionObject(
            "o1", "airplane", 0.9, NOW, (1.0, 1.0, 100.0, 100.0),
            depth_m=30.0, depth_variance_m2=1.0, relative_velocity_mps=-10.0, ttc_s=3.0,
        ),))
        decision = DeterministicDecisionEngine().decide(fusion.snapshot(NOW))
        self.assertEqual(decision.intent, AdvisoryIntent.REQUEST_REROUTE)

    def test_rejects_out_of_order_sensor_update(self) -> None:
        fusion = synchronizer()
        with self.assertRaises(ValueError):
            fusion.update(SensorKind.IMU, ImuSample(
                SensorHeader(NOW - 1, 2, "imu", "base_link", 0.9),
                (0.0, 0.0, 9.81), (0.0, 0.0, 0.0),
            ))


if __name__ == "__main__":
    unittest.main()

