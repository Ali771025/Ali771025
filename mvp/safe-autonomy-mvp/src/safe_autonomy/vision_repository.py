from __future__ import annotations

import hashlib
import json
import time
from uuid import uuid4

from .database import Database
from .vision_contracts import ModuleHealth, ProcessedFrame, SyncRecord


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class VisionRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def start_stream(
        self,
        name: str,
        source_type: str,
        input_pipeline: str,
        output_pipeline: str | None,
        width_px: int,
        height_px: int,
        fps: float,
        pixel_format: str,
        tracker_backend: str,
        model_version: str,
        configuration: dict[str, object],
        started_at_ms: int | None = None,
        stream_id: str | None = None,
    ) -> str:
        identity = stream_id or str(uuid4())
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO camera_streams(
                    stream_id, name, source_type, input_pipeline, output_pipeline,
                    width_px, height_px, fps, pixel_format, tracker_backend,
                    model_version, configuration_json, status, started_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'RUNNING', ?)""",
                (
                    identity, name, source_type, input_pipeline, output_pipeline,
                    width_px, height_px, fps, pixel_format, tracker_backend,
                    model_version, _json(configuration),
                    started_at_ms if started_at_ms is not None else time.time_ns() // 1_000_000,
                ),
            )
        return identity

    def save_processed_frame(self, frame: ProcessedFrame, sync: SyncRecord | None = None) -> None:
        meta = frame.captured.metadata
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO vision_frames(
                    vision_frame_id, stream_id, sequence_no, pts_ns, dts_ns, duration_ns,
                    host_monotonic_ms, captured_at_ms, width_px, height_px,
                    capture_latency_ms, inference_latency_ms, publish_latency_ms,
                    end_to_end_latency_ms, dropped_before, object_count, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PROCESSED')""",
                (
                    meta.vision_frame_id, meta.stream_id, meta.sequence_no, meta.pts_ns,
                    meta.dts_ns, meta.duration_ns, meta.host_monotonic_ms, meta.captured_at_ms,
                    meta.width_px, meta.height_px, frame.captured.capture_latency_ms,
                    frame.inference_latency_ms, frame.publish_latency_ms,
                    frame.end_to_end_latency_ms, frame.captured.dropped_before, len(frame.objects),
                ),
            )
            connection.executemany(
                """INSERT INTO vision_objects(
                    vision_frame_id, object_id, track_id, class_id, class_name,
                    confidence, x1_px, y1_px, x2_px, y2_px, tracker_backend
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        meta.vision_frame_id, obj.object_id, obj.track_id, obj.class_id,
                        obj.class_name, obj.confidence, *obj.bbox_xyxy_px, obj.tracker_backend,
                    )
                    for obj in frame.objects
                ],
            )
            if sync is not None:
                connection.execute(
                    """INSERT INTO sensor_vision_sync(
                        sync_id, vision_frame_id, telemetry_frame_id, skew_ms,
                        status, policy_version, created_at_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        sync.sync_id, sync.vision_frame_id, sync.telemetry_frame_id,
                        sync.skew_ms, sync.status.value, sync.policy_version, sync.created_at_ms,
                    ),
                )

    def save_health(self, health: ModuleHealth) -> None:
        created = health.created_at_ms or time.time_ns() // 1_000_000
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO module_health_events(
                    event_id, module_id, status, host_monotonic_ms, latency_ms,
                    queue_depth, dropped_count, details_json, created_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    health.event_id, health.module_id, health.status.value,
                    health.host_monotonic_ms, health.latency_ms, health.queue_depth,
                    health.dropped_count, _json(health.details), created,
                ),
            )

    def save_wiring_revision(
        self,
        configuration: dict[str, object],
        valid: bool,
        reasons: tuple[str, ...],
        created_at_ms: int | None = None,
    ) -> str:
        canonical = _json(configuration)
        checksum = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        revision_id = str(uuid4())
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO wiring_revisions(
                    revision_id, schema_version, checksum_sha256, configuration_json,
                    validation_status, validation_reasons_json, created_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    revision_id, str(configuration.get("schema_version", "unknown")), checksum,
                    canonical, "VALID" if valid else "INVALID", _json(reasons),
                    created_at_ms if created_at_ms is not None else time.time_ns() // 1_000_000,
                ),
            )
        return revision_id

    def finish_stream(self, stream_id: str, error: str | None = None) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """UPDATE camera_streams
                   SET status=?, completed_at_ms=?, error_message=? WHERE stream_id=?""",
                ("FAILED" if error else "STOPPED", time.time_ns() // 1_000_000, error, stream_id),
            )
