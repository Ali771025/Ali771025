from __future__ import annotations

import unittest

from safe_autonomy.assurance_contracts import DynamicTrack
from safe_autonomy.dynamic_risk import DynamicRiskOverlay
from safe_autonomy.energy_model import EnergyPolicy, RouteEnergyEstimator
from safe_autonomy.mission_contracts import CoordinateSystem, MapFormat, MissionMap, RouteCandidate, RoutePoint3D


def map_fixture() -> MissionMap:
    return MissionMap("map", "fixture", MapFormat.FIXTURE, "a" * 64, 1, CoordinateSystem.LOCAL_ENU, 20, 20, 1.0, 0.0, 0.0, bytes(400), (0.0,) * 400)


def route_fixture(duration_s: float = 60.0) -> RouteCandidate:
    points = (
        RoutePoint3D(0, 0, 0, 0, 20, 0, 0),
        RoutePoint3D(10, 0, 10, 0, 30, duration_s, 10),
    )
    return RouteCandidate("request", 1, 10, 14.1, duration_s, 0, None, 1, points)


class DynamicRiskTests(unittest.TestCase):
    def test_fresh_high_confidence_track_blocks_near_term_cells(self) -> None:
        track = DynamicTrack("t1", 5, 5, 1, 0, 1, 0.95, 1000)
        result = DynamicRiskOverlay(safety_margin_m=1).apply(map_fixture(), (track,), 1050)
        self.assertEqual(result.occupancy_at(result.to_cell(5.05, 5)), 1)
        self.assertGreater(result.risk_at(result.to_cell(7.05, 5)), 0)

    def test_stale_track_is_ignored(self) -> None:
        original = map_fixture()
        track = DynamicTrack("t1", 5, 5, 0, 0, 1, 0.95, 0)
        result = DynamicRiskOverlay(maximum_track_age_ms=100).apply(original, (track,), 1000)
        self.assertEqual(result.occupancy, original.occupancy)
        self.assertEqual(result.risk, original.risk)


class EnergyTests(unittest.TestCase):
    def test_feasible_route_preserves_reserve(self) -> None:
        result = RouteEnergyEstimator(EnergyPolicy(cruise_power_w=100)).evaluate(route_fixture(), 1000, 80, 2)
        self.assertTrue(result.feasible)
        self.assertGreater(result.margin_wh, 0)

    def test_infeasible_route_fails_closed(self) -> None:
        result = RouteEnergyEstimator(EnergyPolicy(cruise_power_w=2000)).evaluate(route_fixture(3600), 500, 30, 12)
        self.assertFalse(result.feasible)
        self.assertLess(result.margin_wh, 0)
