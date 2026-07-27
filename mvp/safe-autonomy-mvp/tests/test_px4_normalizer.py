from __future__ import annotations

import unittest
from types import SimpleNamespace

from safe_autonomy.px4_normalizer import Px4MessageNormalizer


class Px4NormalizerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.normalizer = Px4MessageNormalizer()

    def test_normalizes_gps_units_and_quality(self) -> None:
        message = SimpleNamespace(
            timestamp=1_000_000, lat=357000000, lon=513000000, alt=1_250_000,
            vel_n_m_s=1.0, vel_e_m_s=2.0, vel_d_m_s=-0.5,
            eph=0.8, epv=1.2, fix_type=3,
        )
        sample = self.normalizer.gps(message)
        self.assertEqual(sample.header.timestamp_ms, 1_000)
        self.assertAlmostEqual(sample.latitude_deg, 35.7)
        self.assertAlmostEqual(sample.longitude_deg, 51.3)
        self.assertAlmostEqual(sample.altitude_msl_m, 1_250.0)
        self.assertGreater(sample.header.quality, 0.9)

    def test_normalizes_battery_fraction_to_percent(self) -> None:
        sample = self.normalizer.battery(SimpleNamespace(
            timestamp=1_000_000, remaining=0.42, voltage_v=14.8,
            current_a=8.0, temperature=35.0,
        ))
        self.assertAlmostEqual(sample.remaining_percent, 42.0)

    def test_imu_clipping_reduces_quality(self) -> None:
        sample = self.normalizer.imu(SimpleNamespace(
            timestamp=1_000_000, accelerometer_clipping=[1, 0, 0],
            accelerometer_m_s2=[0.0, 0.0, 9.81], gyro_rad=[0.0, 0.0, 0.0],
        ))
        self.assertLess(sample.header.quality, 0.6)


if __name__ == "__main__":
    unittest.main()

