from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from safe_autonomy.audit import JsonlAuditLog
from safe_autonomy.contracts import Intent, MissionState, Obstacle, Pose2D, Vector2, Verdict
from safe_autonomy.mission import MissionManager
from safe_autonomy.planner import DeterministicAStarPlanner, GridMap
from safe_autonomy.safety import Geofence, SafetyPolicy, SafetySupervisor
from safe_autonomy.world_model import WorldModel, WorldModelPolicy


NOW = 10_000


def build_world(*, timestamp_ms: int = NOW, battery: float = 80.0):
    model = WorldModel(WorldModelPolicy(pose_max_age_ms=250, obstacle_max_age_ms=500, battery_max_age_ms=1_000, minimum_quality=0.6))
    model.update_pose(Pose2D(Vector2(1.0, 1.0), 0.0, timestamp_ms, 0.95, 0.04))
    model.update_obstacles((Obstacle("o1", Vector2(8.0, 8.0), 1.0, 0.95, timestamp_ms, 0.04),))
    model.update_battery(battery, timestamp_ms)
    return model.snapshot(NOW)


def build_safety() -> SafetySupervisor:
    return SafetySupervisor(SafetyPolicy(
        world_model_max_age_ms=500,
        minimum_battery_percent=25.0,
        maximum_speed_mps=5.0,
        maximum_acceleration_mps2=3.0,
        minimum_obstacle_separation_m=1.0,
        allowed_control_authority="MISSION_MANAGER",
        geofence=Geofence(0.0, 20.0, 0.0, 20.0),
    ))


class ContractTests(unittest.TestCase):
    def test_rejects_invalid_quality(self) -> None:
        with self.assertRaises(ValueError):
            Pose2D(Vector2(0.0, 0.0), 0.0, NOW, 1.2)

    def test_rejects_out_of_order_pose(self) -> None:
        model = WorldModel()
        model.update_pose(Pose2D(Vector2(0.0, 0.0), 0.0, NOW, 1.0))
        with self.assertRaises(ValueError):
            model.update_pose(Pose2D(Vector2(0.0, 0.0), 0.0, NOW - 1, 1.0))

    def test_rejects_future_obstacle_timestamp(self) -> None:
        model = WorldModel()
        model.update_pose(Pose2D(Vector2(0.0, 0.0), 0.0, NOW, 1.0))
        model.update_obstacles((Obstacle("future", Vector2(2.0, 2.0), 1.0, 1.0, NOW + 1),))
        model.update_battery(80.0, NOW)
        with self.assertRaises(ValueError):
            model.snapshot(NOW)


class WorldModelTests(unittest.TestCase):
    def test_stale_sources_are_explicit(self) -> None:
        world = build_world(timestamp_ms=NOW - 1_000)
        self.assertIn("pose", world.stale_sources)
        self.assertIn("obstacle:o1", world.stale_sources)


class PlannerAndSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = build_world()
        self.planner = DeterministicAStarPlanner(GridMap(0.0, 20.0, 0.0, 20.0), 1.0)
        self.safety = build_safety()

    def test_planner_is_deterministic_and_avoids_obstacle(self) -> None:
        first = self.planner.plan("r1", self.world, Vector2(15.0, 15.0), NOW)
        second = self.planner.plan("r2", self.world, Vector2(15.0, 15.0), NOW)
        self.assertEqual(tuple(p.position for p in first.points), tuple(p.position for p in second.points))
        self.assertNotIn(Vector2(8.0, 8.0), tuple(p.position for p in first.points))
        self.assertEqual(self.safety.evaluate(first, self.world, NOW).verdict, Verdict.PASS)

    def test_rejects_unknown_authority(self) -> None:
        trajectory = self.planner.plan("r1", self.world, Vector2(15.0, 15.0), NOW)
        decision = self.safety.evaluate(replace(trajectory, control_authority="OTHER"), self.world, NOW)
        self.assertEqual(decision.verdict, Verdict.REJECT)
        self.assertIn("unknown control authority", decision.reasons)

    def test_rejects_low_battery(self) -> None:
        world = build_world(battery=10.0)
        trajectory = self.planner.plan("r1", world, Vector2(15.0, 15.0), NOW)
        self.assertEqual(self.safety.evaluate(trajectory, world, NOW).verdict, Verdict.REJECT)

    def test_rejects_stale_source(self) -> None:
        world = build_world(timestamp_ms=NOW - 1_000)
        trajectory = self.planner.plan("r1", world, Vector2(15.0, 15.0), NOW)
        self.assertEqual(self.safety.evaluate(trajectory, world, NOW).verdict, Verdict.REJECT)


class MissionTests(unittest.TestCase):
    def test_nominal_intent_reaches_ready_and_audits(self) -> None:
        world = build_world()
        with tempfile.TemporaryDirectory() as directory:
            audit_path = Path(directory) / "audit.jsonl"
            manager = MissionManager(
                DeterministicAStarPlanner(GridMap(0.0, 20.0, 0.0, 20.0), 1.0),
                build_safety(),
                JsonlAuditLog(audit_path),
            )
            decision = manager.handle_intent(Intent.START_MISSION, "r1", world, NOW, Vector2(15.0, 15.0))
            self.assertIsNotNone(decision)
            self.assertEqual(manager.state, MissionState.READY)
            self.assertEqual(len(audit_path.read_text(encoding="utf-8").splitlines()), 2)

    def test_hold_intent_never_invokes_planner(self) -> None:
        world = build_world()
        with tempfile.TemporaryDirectory() as directory:
            manager = MissionManager(
                DeterministicAStarPlanner(GridMap(0.0, 20.0, 0.0, 20.0), 1.0),
                build_safety(),
                JsonlAuditLog(Path(directory) / "audit.jsonl"),
            )
            self.assertIsNone(manager.handle_intent(Intent.HOLD, "r1", world, NOW))
            self.assertEqual(manager.state, MissionState.HOLD)


if __name__ == "__main__":
    unittest.main()
