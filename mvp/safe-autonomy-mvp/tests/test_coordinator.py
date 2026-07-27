from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from safe_autonomy.ai_demo import run_demo


class CoordinatorIntegrationTests(unittest.TestCase):
    def test_incomplete_depth_requests_sensor_update_with_perception_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_demo(Path(directory) / "coordinator.sqlite3", "incomplete_depth")
        self.assertEqual(result["decision"]["intent"], "REQUEST_SENSOR_UPDATE")
        self.assertTrue(result["evidence_gate"]["passed"])
        self.assertEqual(result["evidence"][0]["section"], "ادراک")

    def test_low_battery_lands_with_energy_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_demo(Path(directory) / "coordinator.sqlite3", "low_battery")
        self.assertEqual(result["decision"]["intent"], "LAND")
        self.assertTrue(result["proposal"]["requires_human_confirmation"])
        self.assertEqual(result["evidence"][0]["section"], "انرژی")


if __name__ == "__main__":
    unittest.main()

