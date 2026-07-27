from __future__ import annotations

import json
import sqlite3
import time
from importlib.metadata import distribution
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from threading import RLock
from typing import Iterator
from uuid import uuid4

from .contracts import AuditEvent, SafetyDecision, Trajectory, WorldSnapshot
from .perception import Detection2D, VideoMetadata


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class Database:
    """SQLite development database with migrations, FK enforcement and WAL."""

    def __init__(self, path: str | Path, migrations_dir: str | Path | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if migrations_dir:
            self.migrations_dir = Path(migrations_dir)
        else:
            source_migrations = Path(__file__).resolve().parents[2] / "migrations"
            if source_migrations.is_dir():
                self.migrations_dir = source_migrations
            else:
                self.migrations_dir = Path(
                    distribution("safe-autonomy-mvp").locate_file("safe_autonomy_migrations")
                )
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.execute("PRAGMA synchronous = NORMAL")
        self._lock = RLock()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                yield self._connection
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise

    @property
    def _sqlite_version(self) -> tuple[int, ...]:
        row = self._connection.execute("SELECT sqlite_version()").fetchone()
        return tuple(int(part) for part in str(row[0]).split("."))

    @staticmethod
    def _split_sql_statements(sql: str) -> list[str]:
        """Split a SQL script into individual statements.

        A naive ``sql.split(';')`` breaks when bodies contain semicolons (e.g.
        inside trigger definitions).  This helper splits on top-level
        semicolons while respecting SQL string literals, preserving trigger
        bodies verbatim.
        """
        statements: list[str] = []
        buf: list[str] = []
        in_single = False
        in_double = False
        i = 0
        while i < len(sql):
            ch = sql[i]
            nxt = sql[i + 1] if i + 1 < len(sql) else ""
            # Line comments
            if not in_single and not in_double and ch == "-" and nxt == "-":
                end = sql.find("\n", i)
                if end == -1:
                    break
                buf.append(sql[i:end])
                i = end
                continue
            # Block comments
            if not in_single and not in_double and ch == "/" and nxt == "*":
                end = sql.find("*/", i + 2)
                if end == -1:
                    buf.append(sql[i:])
                    break
                buf.append(sql[i:end + 2])
                i = end + 2
                continue
            if ch == "'" and not in_double:
                # Escape ''
                in_single = not in_single
                buf.append(ch)
                i += 1
                continue
            if ch == '"' and not in_single:
                in_double = not in_double
                buf.append(ch)
                i += 1
                continue
            if ch == ";" and not in_single and not in_double:
                stmt = "".join(buf).strip()
                if stmt:
                    statements.append(stmt)
                buf = []
                i += 1
                continue
            buf.append(ch)
            i += 1
        tail = "".join(buf).strip()
        if tail:
            statements.append(tail)
        return statements

    def migrate(self) -> None:
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at_ms INTEGER NOT NULL)"
        )
        applied = {row[0] for row in self._connection.execute("SELECT version FROM schema_migrations")}
        sqlite_ver = self._sqlite_version
        for path in sorted(self.migrations_dir.glob("[0-9][0-9][0-9]_*.sql")):
            version = int(path.name.split("_", 1)[0])
            if version in applied:
                continue
            sql = path.read_text(encoding="utf-8")
            with self._lock:
                # Use executescript which understands SQL delimiters inside
                # trigger bodies correctly. executescript commits the current
                # implicit transaction before running the script, so we wrap
                # the migration + version row insert inside our own explicit
                # transaction to keep them atomic.
                try:
                    self._connection.execute("BEGIN IMMEDIATE")
                    self._connection.executescript(sql)
                    self._connection.execute(
                        "INSERT INTO schema_migrations(version, name, applied_at_ms) VALUES (?, ?, ?)",
                        (version, path.name, int(time.time() * 1000)),
                    )
                    self._connection.commit()
                except Exception:
                    self._connection.rollback()
                    raise
        _ = sqlite_ver  # version information retained for future guards

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connection


class AutonomyRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def start_video_run(
        self,
        metadata: VideoMetadata,
        backend: str,
        model_version: str,
        started_at_ms: int,
        configuration: dict[str, object] | None = None,
    ) -> str:
        run_id = str(uuid4())
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO video_runs(
                    run_id, source_name, source_sha256, source_size_bytes, duration_ms,
                    width_px, height_px, fps, codec, backend, model_version,
                    started_at_ms, status, created_at_ms, configuration_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'RUNNING', ?, ?)""",
                (
                    run_id, metadata.source_name, metadata.sha256, metadata.size_bytes,
                    metadata.duration_ms, metadata.width_px, metadata.height_px,
                    metadata.fps, metadata.codec, backend, model_version,
                    started_at_ms, started_at_ms, _json(configuration or {}),
                ),
            )
        return run_id

    def save_detection(self, run_id: str, detection: Detection2D, created_at_ms: int) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO detections(
                    detection_id, run_id, frame_index, video_timestamp_ms, class_id,
                    class_name, confidence, x1_px, y1_px, x2_px, y2_px, track_id,
                    depth_m, depth_variance_m2, model_version, calibration_version, created_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    detection.detection_id, run_id, detection.frame_index,
                    detection.video_timestamp_ms, detection.class_id, detection.class_name,
                    detection.confidence, detection.x1_px, detection.y1_px,
                    detection.x2_px, detection.y2_px, detection.track_id,
                    detection.depth_m, detection.depth_variance_m2,
                    detection.model_version, detection.calibration_version, created_at_ms,
                ),
            )

    def finish_video_run(self, run_id: str, completed_at_ms: int, error: str | None = None) -> None:
        status = "FAILED" if error else "SUCCEEDED"
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE video_runs SET completed_at_ms=?, status=?, error_message=? WHERE run_id=?",
                (completed_at_ms, status, error, run_id),
            )

    def save_world_snapshot(self, world: WorldSnapshot) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO world_snapshots(
                    snapshot_id, created_at_ms, pose_x_m, pose_y_m, heading_rad,
                    pose_timestamp_ms, pose_quality, pose_covariance_m2, frame_id,
                    battery_percent, battery_timestamp_ms, source_sequence,
                    stale_sources_json, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    world.snapshot_id, world.created_at_ms, world.pose.position.x_m,
                    world.pose.position.y_m, world.pose.heading_rad, world.pose.timestamp_ms,
                    world.pose.quality, world.pose.covariance_m2, world.pose.frame_id,
                    world.battery_percent, world.battery_timestamp_ms,
                    world.source_sequence, _json(world.stale_sources), world.schema_version,
                ),
            )
            connection.executemany(
                """INSERT OR IGNORE INTO world_obstacles(
                    snapshot_id, obstacle_id, x_m, y_m, radius_m, confidence,
                    timestamp_ms, position_variance_m2
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        world.snapshot_id, obstacle.obstacle_id, obstacle.position.x_m,
                        obstacle.position.y_m, obstacle.radius_m, obstacle.confidence,
                        obstacle.timestamp_ms, obstacle.position_variance_m2,
                    )
                    for obstacle in world.obstacles
                ],
            )

    def save_trajectory(self, trajectory: Trajectory) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO trajectories(
                    trajectory_id, request_id, world_snapshot_id, generated_at_ms,
                    control_authority, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    trajectory.trajectory_id, trajectory.request_id,
                    trajectory.world_snapshot_id, trajectory.generated_at_ms,
                    trajectory.control_authority, trajectory.schema_version,
                ),
            )
            connection.executemany(
                """INSERT OR IGNORE INTO trajectory_points(
                    trajectory_id, sequence_no, x_m, y_m, time_from_start_s, speed_mps
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (
                        trajectory.trajectory_id, index, point.position.x_m,
                        point.position.y_m, point.time_from_start_s, point.speed_mps,
                    )
                    for index, point in enumerate(trajectory.points)
                ],
            )

    def save_safety_decision(self, decision: SafetyDecision) -> int:
        with self.database.transaction() as connection:
            cursor = connection.execute(
                """INSERT INTO safety_decisions(
                    request_id, trajectory_id, evaluated_at_ms, verdict, schema_version
                ) VALUES (?, ?, ?, ?, ?)""",
                (
                    decision.request_id, decision.trajectory_id,
                    decision.evaluated_at_ms, decision.verdict.value,
                    decision.schema_version,
                ),
            )
            decision_id = int(cursor.lastrowid)
            connection.executemany(
                """INSERT INTO safety_gate_results(
                    decision_id, sequence_no, gate, passed, reason, observed_json, limit_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        decision_id, index, gate.gate, int(gate.passed), gate.reason,
                        _json(gate.observed), _json(gate.limit),
                    )
                    for index, gate in enumerate(decision.gates)
                ],
            )
        return decision_id

    def save_audit_event(self, event: AuditEvent) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO audit_events(
                    event_type, timestamp_ms, correlation_id, payload_json, schema_version
                ) VALUES (?, ?, ?, ?, ?)""",
                (
                    event.event_type, event.timestamp_ms, event.correlation_id,
                    _json(asdict(event)["payload"]), event.schema_version,
                ),
            )

    def video_run_summary(self, run_id: str) -> dict[str, object]:
        row = self.database.connection.execute(
            """SELECT v.*, COUNT(d.detection_id) AS detection_count
               FROM video_runs v LEFT JOIN detections d ON d.run_id=v.run_id
               WHERE v.run_id=? GROUP BY v.run_id""",
            (run_id,),
        ).fetchone()
        if row is None:
            raise KeyError(run_id)
        return dict(row)
