from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from safe_autonomy.audit import DatabaseAuditLog
from safe_autonomy.contracts import AuditEvent, Intent, Obstacle, Pose2D, Vector2, Verdict
from safe_autonomy.database import AutonomyRepository, Database
from safe_autonomy.db_cli import inspect_database
from safe_autonomy.mission import MissionManager
from safe_autonomy.perception import Detection2D, VideoMetadata
from safe_autonomy.planner import DeterministicAStarPlanner, GridMap
from safe_autonomy.safety import Geofence, SafetyPolicy, SafetySupervisor
from safe_autonomy.world_model import WorldModel


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp.name) / "test.sqlite3")
        self.database.migrate()
        self.repository = AutonomyRepository(self.database)

    def tearDown(self) -> None:
        self.database.close()
        self.temp.cleanup()

    def test_migration_is_idempotent_and_foreign_keys_enabled(self) -> None:
        self.database.migrate()
        version_count = self.database.connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        foreign_keys = self.database.connection.execute("PRAGMA foreign_keys").fetchone()[0]
        # 001..007 shipped migrations
        self.assertEqual(version_count, 7)
        self.assertEqual(foreign_keys, 1)
        summary = inspect_database(self.database.path)
        self.assertEqual(summary["integrity"], "ok")

    def test_video_run_and_detection_are_persisted(self) -> None:
        metadata = VideoMetadata("sample.mp4", "a" * 64, 100, 1000, 400, 224, 25.0, "h264")
        run_id = self.repository.start_video_run(metadata, "fixture", "fixture-v1", 100, {"sample_fps": 2.0})
        detection = Detection2D(
            "d1", 0, 0, 4, "airplane", 0.9,
            10.0, 20.0, 200.0, 180.0, "fixture-v1",
        )
        self.repository.save_detection(run_id, detection, 101)
        self.repository.finish_video_run(run_id, 102)
        summary = self.repository.video_run_summary(run_id)
        self.assertEqual(summary["status"], "SUCCEEDED")
        self.assertEqual(summary["detection_count"], 1)
        self.assertIn('"sample_fps":2.0', summary["configuration_json"])

    def test_audit_event_is_persisted(self) -> None:
        sink = DatabaseAuditLog(self.repository)
        sink.append(AuditEvent("TEST", 100, "correlation-1", {"ok": True}))
        count = self.database.connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        self.assertEqual(count, 1)

    def test_full_safety_bundle_is_transactionally_persisted(self) -> None:
        model = WorldModel()
        model.update_pose(Pose2D(Vector2(1.0, 1.0), 0.0, 100, 0.95))
        model.update_obstacles((Obstacle("o1", Vector2(8.0, 8.0), 1.0, 0.95, 100),))
        model.update_battery(80.0, 100)
        world = model.snapshot(100)
        safety = SafetySupervisor(SafetyPolicy(
            500, 25.0, 5.0, 3.0, 1.0, "MISSION_MANAGER",
            Geofence(0.0, 20.0, 0.0, 20.0),
        ))
        manager = MissionManager(
            DeterministicAStarPlanner(GridMap(0.0, 20.0, 0.0, 20.0), 1.0),
            safety,
            DatabaseAuditLog(self.repository),
            self.repository,
        )
        decision = manager.handle_intent(Intent.START_MISSION, "db-r1", world, 100, Vector2(15.0, 15.0))
        self.assertEqual(decision.verdict, Verdict.PASS)
        expected_counts = {
            "world_snapshots": 1,
            "trajectories": 1,
            "safety_decisions": 1,
            "safety_gate_results": 8,
            "audit_events": 2,
        }
        for table, expected in expected_counts.items():
            with self.subTest(table=table):
                count = self.database.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                self.assertEqual(count, expected)


if __name__ == "__main__":
    unittest.main()
