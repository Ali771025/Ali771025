from __future__ import annotations

import json
import time
from dataclasses import asdict

from .database import Database
from .sensor_contracts import SensorKind, SensorSample, TelemetryFrame, sensor_payload


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class TelemetryRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def save_sample(self, kind: SensorKind, sample: SensorSample, created_at_ms: int | None = None) -> None:
        header = sample.header
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO telemetry_samples(
                    sample_id, sensor_kind, timestamp_ms, sequence_no, source, frame_id,
                    quality, calibration_version, payload_json, created_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    header.sample_id, kind.value, header.timestamp_ms, header.sequence_no,
                    header.source, header.frame_id, header.quality,
                    header.calibration_version, _json(sensor_payload(sample)),
                    created_at_ms if created_at_ms is not None else int(time.time() * 1000),
                ),
            )

    def save_frame(self, frame: TelemetryFrame) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO telemetry_frames(
                    telemetry_frame_id, created_at_ms, local_x_m, local_y_m, altitude_m,
                    velocity_north_mps, velocity_east_mps, velocity_down_mps,
                    battery_percent, overall_quality, timestamp_skew_ms,
                    stale_sources_json, source_sample_ids_json, schema_version,
                    host_monotonic_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    frame.telemetry_frame_id, frame.created_at_ms, frame.local_x_m,
                    frame.local_y_m, frame.altitude_m, frame.velocity_north_mps,
                    frame.velocity_east_mps, frame.velocity_down_mps,
                    frame.battery_percent, frame.overall_quality, frame.timestamp_skew_ms,
                    _json(frame.stale_sources), _json(frame.source_sample_ids),
                    frame.schema_version, frame.host_monotonic_ms,
                ),
            )
            connection.executemany(
                """INSERT OR IGNORE INTO telemetry_perception_objects(
                    telemetry_frame_id, object_id, class_name, confidence, timestamp_ms,
                    bbox_json, track_id, depth_m, depth_variance_m2,
                    relative_velocity_mps, ttc_s
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        frame.telemetry_frame_id, obj.object_id, obj.class_name,
                        obj.confidence, obj.timestamp_ms, _json(obj.bbox_xyxy_px),
                        obj.track_id, obj.depth_m, obj.depth_variance_m2,
                        obj.relative_velocity_mps, obj.ttc_s,
                    )
                    for obj in frame.perception_objects
                ],
            )

    def save_synchronizer(self, synchronizer, frame: TelemetryFrame) -> None:
        for kind, sample in synchronizer.samples():
            self.save_sample(kind, sample, frame.created_at_ms)
        self.save_frame(frame)
