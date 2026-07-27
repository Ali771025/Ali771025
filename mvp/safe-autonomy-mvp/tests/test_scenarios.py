from __future__ import annotations

import unittest

from safe_autonomy.simulator import run_scenario


class ScenarioTests(unittest.TestCase):
    def test_nominal_passes(self) -> None:
        result = run_scenario("nominal")
        self.assertEqual(result["decision"]["verdict"], "PASS")

    def test_faults_fail_closed(self) -> None:
        for scenario in ("stale_state", "low_battery", "authority_conflict"):
            with self.subTest(scenario=scenario):
                result = run_scenario(scenario)
                self.assertEqual(result["decision"]["verdict"], "REJECT")
                self.assertEqual(result["mission_state"], "HOLD")


if __name__ == "__main__":
    unittest.main()
