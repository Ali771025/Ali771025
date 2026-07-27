from __future__ import annotations

import unittest
from dataclasses import replace

from safe_autonomy.observability import LatencyRegistry
from safe_autonomy.route_revalidation import RevalidationPolicy, RouteRevalidator
from test_dynamic_energy_v06 import map_fixture, route_fixture


class RouteRevalidationTests(unittest.TestCase):
    def test_nominal_progress_continues(self) -> None:
        result = RouteRevalidator().evaluate(map_fixture(), route_fixture(), 0.5, 0, 1000)
        self.assertEqual(result.recommendation, "CONTINUE")

    def test_large_deviation_holds(self) -> None:
        result = RouteRevalidator(RevalidationPolicy(critical_cross_track_m=5)).evaluate(map_fixture(), route_fixture(), 0, 10, 1000)
        self.assertEqual(result.recommendation, "HOLD")
        self.assertIn("CROSS_TRACK_CRITICAL", result.reasons)

    def test_dynamic_block_in_corridor_never_gets_downgraded_by_cooldown(self) -> None:
        mission_map = map_fixture()
        occupancy = bytearray(mission_map.occupancy)
        occupancy[mission_map.index((5, 0))] = 1
        mission_map = replace(mission_map, occupancy=bytes(occupancy))
        monitor = RouteRevalidator(RevalidationPolicy(replan_cooldown_ms=5000))
        first = monitor.evaluate(mission_map, route_fixture(), 0, 0, 1000)
        second = monitor.evaluate(mission_map, route_fixture(), 0, 0, 1500)
        self.assertEqual(first.recommendation, "HOLD")
        self.assertEqual(second.recommendation, "HOLD")

    def test_noncritical_replan_is_debounced(self) -> None:
        monitor = RouteRevalidator(RevalidationPolicy(warning_cross_track_m=1, critical_cross_track_m=10, replan_cooldown_ms=5000))
        first = monitor.evaluate(map_fixture(), route_fixture(), 0, 2, 1000)
        second = monitor.evaluate(map_fixture(), route_fixture(), 0, 2, 1500)
        self.assertEqual(first.recommendation, "REQUEST_REPLAN")
        self.assertEqual(second.recommendation, "MONITOR")


class ObservabilityTests(unittest.TestCase):
    def test_percentiles_and_budget_ratio_are_deterministic(self) -> None:
        registry = LatencyRegistry(20)
        for value in range(1, 11):
            registry.observe("fusion", value)
        snapshot = registry.snapshot("fusion", 8)
        self.assertEqual(snapshot.count, 10)
        self.assertEqual(snapshot.p95_ms, 10)
        self.assertEqual(snapshot.within_budget_ratio, 0.8)

    def test_registry_is_bounded(self) -> None:
        registry = LatencyRegistry(10)
        for value in range(20):
            registry.observe("vision", value)
        snapshot = registry.snapshot("vision", 100)
        self.assertEqual(snapshot.count, 10)
        self.assertEqual(snapshot.minimum_ms, 10)
