from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path

from safe_autonomy.flight_state_analyzer import FlightStateAnalyzer
from safe_autonomy.mission_contracts import FindingSeverity, FlightPhase, SafeRecommendation
from safe_autonomy.scenario_engine import ScenarioEngine, nominal_flight_sample


ROOT = Path(__file__).resolve().parents[1]


class FlightScenarioTests(unittest.TestCase):
    def test_nominal_cruise_continues(self) -> None:
        assessment = FlightStateAnalyzer().analyze(nominal_flight_sample(), 2_000, FlightPhase.CRUISE)
        self.assertEqual(assessment.inferred_phase, FlightPhase.CRUISE)
        self.assertEqual(assessment.recommendation, SafeRecommendation.CONTINUE)
        self.assertEqual(assessment.highest_severity, FindingSeverity.INFO)
        self.assertEqual(assessment.health_score, 100)

    def test_multiple_faults_choose_highest_priority_bounded_action(self) -> None:
        sample = replace(nominal_flight_sample(), battery_percent=10, route_deviation_m=30, camera_healthy=False)
        assessment = FlightStateAnalyzer().analyze(sample, 2_000)
        self.assertEqual(assessment.recommendation, SafeRecommendation.LAND)
        self.assertEqual(assessment.highest_severity, FindingSeverity.CRITICAL)
        self.assertIn("BATTERY_CRITICAL", {finding.code for finding in assessment.findings})

    def test_all_declared_flight_scenarios_pass(self) -> None:
        definitions = ScenarioEngine.load(ROOT / "config/flight_scenarios.json")
        results = ScenarioEngine().run_all(definitions, 10_000)
        self.assertGreaterEqual(len(results), 25)
        failures = {result.definition.scenario_id: result.failure_reason for result in results if not result.passed}
        self.assertEqual(failures, {})


if __name__ == "__main__":
    unittest.main()
