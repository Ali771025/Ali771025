from __future__ import annotations

import time
from dataclasses import dataclass
from .database import Database
from .vision_contracts import FrameMetadata, SyncRecord, SyncStatus


@dataclass(frozen=True, slots=True)
class SynchronizationPolicy:
    max_skew_ms: int = 50
    version: str = "monotonic-nearest-v1"

    def __post_init__(self) -> None:
        if self.max_skew_ms <= 0:
            raise ValueError("max_skew_ms must be positive")


class MultimodalSynchronizer:
    """Matches camera and telemetry only in the same host monotonic clock domain."""

    def __init__(self, database: Database, policy: SynchronizationPolicy | None = None) -> None:
        self.database = database
        self.policy = policy or SynchronizationPolicy()

    def match(self, frame: FrameMetadata, created_at_ms: int | None = None) -> SyncRecord:
        row = self.database.connection.execute(
            """SELECT telemetry_frame_id, host_monotonic_ms
               FROM telemetry_frames
               WHERE host_monotonic_ms IS NOT NULL
               ORDER BY ABS(host_monotonic_ms - ?) ASC
               LIMIT 1""",
            (frame.host_monotonic_ms,),
        ).fetchone()
        now = created_at_ms if created_at_ms is not None else time.time_ns() // 1_000_000
        if row is None:
            return SyncRecord(frame.vision_frame_id, None, None, SyncStatus.MISSING, now, self.policy.version)
        skew = abs(int(row["host_monotonic_ms"]) - frame.host_monotonic_ms)
        status = SyncStatus.MATCHED if skew <= self.policy.max_skew_ms else SyncStatus.TOO_OLD
        telemetry_id = str(row["telemetry_frame_id"]) if status is SyncStatus.MATCHED else None
        return SyncRecord(frame.vision_frame_id, telemetry_id, skew, status, now, self.policy.version)
