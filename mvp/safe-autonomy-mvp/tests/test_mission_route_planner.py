from __future__ import annotations

import unittest
from dataclasses import replace

from safe_autonomy.mission_analysis import fixture_map
from safe_autonomy.mission_contracts import RoutePolicy, RouteRequest
from safe_autonomy.mission_route_planner import MultiCriteriaAStarPlanner
from safe_autonomy.planner import PlanningError


class MissionRoutePlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mission_map = fixture_map()
        self.request = RouteRequest(
            self.mission_map.map_id, 8, 8, 108, 68, 25, 60,
            RoutePolicy(obstacle_inflation_m=2, requested_alternatives=3, minimum_distinctness=0.15),
            request_id="route-test",
        )

    def test_primary_and_alternative_routes_are_safe_and_deterministic(self) -> None:
        planner = MultiCriteriaAStarPlanner(self.mission_map)
        first = planner.plan(self.request)
        second = planner.plan(self.request)
        self.assertGreaterEqual(len(first), 2)
        self.assertLessEqual(len(first), 3)
        self.assertEqual(
            [[(point.cell_x, point.cell_y) for point in item.points] for item in first],
            [[(point.cell_x, point.cell_y) for point in item.points] for item in second],
        )
        for candidate in first:
            self.assertTrue(candidate.valid)
            self.assertGreater(candidate.length_m, 0)
            self.assertGreater(candidate.estimated_duration_s, 0)
            for point in candidate.points:
                self.assertEqual(self.mission_map.occupancy_at((point.cell_x, point.cell_y)), 0)
        self.assertGreater(first[1].distinctness, 0)

    def test_blocked_start_is_rejected(self) -> None:
        blocked = RouteRequest(
            self.mission_map.map_id, 0, 0, 108, 68, 25, 60,
            RoutePolicy(requested_alternatives=1), request_id="blocked",
        )
        with self.assertRaises(PlanningError):
            MultiCriteriaAStarPlanner(self.mission_map).plan(blocked)

    def test_request_for_other_map_is_rejected(self) -> None:
        wrong = RouteRequest(
            "other-map", 8, 8, 108, 68, 25, 60,
            RoutePolicy(requested_alternatives=1), request_id="wrong-map",
        )
        with self.assertRaises(PlanningError):
            MultiCriteriaAStarPlanner(self.mission_map).plan(wrong)

    def test_elevation_layer_enforces_terrain_clearance(self) -> None:
        elevated = replace(
            self.mission_map,
            map_id="elevated-map",
            elevation_m=tuple(50.0 for _ in self.mission_map.occupancy),
        )
        request = RouteRequest(
            elevated.map_id, 8, 8, 108, 68, 70, 60,
            RoutePolicy(
                obstacle_inflation_m=2, minimum_terrain_clearance_m=20,
                requested_alternatives=1,
            ),
            request_id="terrain-route",
        )
        candidate = MultiCriteriaAStarPlanner(elevated).plan(request)[0]
        self.assertTrue(candidate.valid)
        self.assertAlmostEqual(candidate.minimum_clearance_m, 20.0)
        self.assertTrue(all(point.altitude_m >= 70.0 for point in candidate.points))


if __name__ == "__main__":
    unittest.main()
