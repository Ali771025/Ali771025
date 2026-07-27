from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from safe_autonomy.database import Database
from safe_autonomy.multimodal_sync import MultimodalSynchronizer, SynchronizationPolicy
from safe_autonomy.sensor_contracts import TelemetryFrame
from safe_autonomy.telemetry_repository import TelemetryRepository
from safe_autonomy.vision_contracts import (
    CapturedFrame,
    FrameMetadata,
    HealthStatus,
    ModuleHealth,
    ProcessedFrame,
    SyncStatus,
    TrackedObject,
)
from safe_autonomy.vision_repository import VisionRepository
from safe_autonomy.wiring import load_wiring, validate_wiring


ROOT = Path(__file__).resolve().parents[1]


def telemetry(identity: str, host_ms: int) -> TelemetryFrame:
    return TelemetryFrame(
        identity, 1_000, 0.0, 0.0, 10.0, 1.0, 0.0, 0.0,
        80.0, 0.9, 5, (), (), host_monotonic_ms=host_ms,
    )


class MultimodalVisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp.name) / "vision.sqlite3")
        self.database.migrate()
        self.telemetry_repository = TelemetryRepository(self.database)
        self.vision_repository = VisionRepository(self.database)
        self.stream_id = self.vision_repository.start_stream(
            "test", "TEST", "test input", None, 640, 480, 25.0,
            "BGR", "fixture", "fixture-v1", {"fixture": True}, stream_id="stream-1",
        )

    def tearDown(self) -> None:
        self.database.close()
        self.temp.cleanup()

    def test_nearest_monotonic_telemetry_is_matched_and_persisted(self) -> None:
        self.telemetry_repository.save_frame(telemetry("telemetry-1", 1_000))
        metadata = FrameMetadata(self.stream_id, 0, 1_030, 2_000, 640, 480, pts_ns=123)
        synchronizer = MultimodalSynchronizer(self.database, SynchronizationPolicy(50))
        sync = synchronizer.match(metadata, 2_001)
        self.assertEqual(sync.status, SyncStatus.MATCHED)
        self.assertEqual(sync.telemetry_frame_id, "telemetry-1")
        self.assertEqual(sync.skew_ms, 30)
        tracked = TrackedObject("object-1", 7, 0, "target", 0.9, (10, 20, 100, 120), "fixture")
        processed = ProcessedFrame(CapturedFrame(metadata, None), (tracked,), 8.0, 2.0, 15.0)
        self.vision_repository.save_processed_frame(processed, sync)
        self.assertEqual(self.database.connection.execute("SELECT COUNT(*) FROM vision_frames").fetchone()[0], 1)
        row = self.database.connection.execute("SELECT track_id FROM vision_objects").fetchone()
        self.assertEqual(row[0], 7)
        status = self.database.connection.execute("SELECT status FROM sensor_vision_sync").fetchone()[0]
        self.assertEqual(status, "MATCHED")

    def test_stale_or_missing_telemetry_never_fabricates_a_match(self) -> None:
        metadata = FrameMetadata(self.stream_id, 0, 1_000, 2_000, 640, 480)
        synchronizer = MultimodalSynchronizer(self.database, SynchronizationPolicy(25))
        self.assertEqual(synchronizer.match(metadata).status, SyncStatus.MISSING)
        self.telemetry_repository.save_frame(telemetry("telemetry-old", 900))
        record = synchronizer.match(metadata)
        self.assertEqual(record.status, SyncStatus.TOO_OLD)
        self.assertIsNone(record.telemetry_frame_id)
        self.assertEqual(record.skew_ms, 100)

    def test_health_and_validated_wiring_are_audited(self) -> None:
        health = ModuleHealth("camera_ingest", HealthStatus.HEALTHY, 1_000, 5.0, 1, 2, {"ok": True})
        self.vision_repository.save_health(health)
        wiring = load_wiring(ROOT / "config/system.wiring.json")
        problems = validate_wiring(wiring)
        self.vision_repository.save_wiring_revision(wiring, not problems, problems, 2_000)
        details = self.database.connection.execute("SELECT details_json FROM module_health_events").fetchone()[0]
        self.assertEqual(json.loads(details), {"ok": True})
        status = self.database.connection.execute("SELECT validation_status FROM wiring_revisions").fetchone()[0]
        self.assertEqual(status, "VALID")


if __name__ == "__main__":
    unittest.main()
