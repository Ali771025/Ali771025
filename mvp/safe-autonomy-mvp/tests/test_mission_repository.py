from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from safe_autonomy.database import Database
from safe_autonomy.flight_state_analyzer import FlightStateAnalyzer
from safe_autonomy.map_ingestion import MapAnalyzer
from safe_autonomy.mission_analysis import fixture_map
from safe_autonomy.mission_contracts import RoutePolicy, RouteRequest
from safe_autonomy.mission_repository import MissionAnalysisRepository
from safe_autonomy.mission_route_planner import MultiCriteriaAStarPlanner
from safe_autonomy.scenario_engine import ScenarioEngine, nominal_flight_sample


ROOT = Path(__file__).resolve().parents[1]


class MissionRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp.name) / "mission.sqlite3")
        self.database.migrate()
        self.repository = MissionAnalysisRepository(self.database)

    def tearDown(self) -> None:
        self.database.close()
        self.temp.cleanup()

    def test_map_route_assessment_and_scenario_are_persisted(self) -> None:
        mission_map = fixture_map()
        analysis = MapAnalyzer().analyze(mission_map)
        self.assertEqual(self.repository.save_map(mission_map, analysis, 1_000), mission_map.map_id)
        self.assertEqual(self.repository.save_map(mission_map, analysis, 1_001), mission_map.map_id)
        loaded = self.repository.load_map(mission_map.map_id)
        self.assertEqual(loaded.occupancy, mission_map.occupancy)
        self.assertEqual(loaded.risk, mission_map.risk)
        request = RouteRequest(
            mission_map.map_id, 8, 8, 108, 68, 25, 60,
            RoutePolicy(requested_alternatives=2, minimum_distinctness=0.15), request_id="persist-route",
        )
        self.repository.start_route(request, 1_010)
        candidates = MultiCriteriaAStarPlanner(loaded).plan(request)
        self.repository.finish_route(request, candidates, 1_020)
        assessment = FlightStateAnalyzer().analyze(nominal_flight_sample(), 2_000)
        self.repository.save_assessment(assessment)
        definition = ScenarioEngine.load(ROOT / "config/flight_scenarios.json")[0]
        self.repository.save_scenario_result(ScenarioEngine().run(definition, 3_000))
        counts = {
            table: self.database.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("mission_maps", "route_plan_requests", "route_candidates", "route_points", "flight_assessments", "scenario_runs", "scenario_events")
        }
        self.assertEqual(counts["mission_maps"], 1)
        self.assertEqual(counts["route_plan_requests"], 1)
        self.assertGreaterEqual(counts["route_candidates"], 1)
        self.assertGreater(counts["route_points"], 2)
        self.assertEqual(counts["flight_assessments"], 2)
        self.assertEqual(counts["scenario_runs"], 1)
        self.assertEqual(counts["scenario_events"], 2)


if __name__ == "__main__":
    unittest.main()
