from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from .contracts import Obstacle, Pose2D, WorldSnapshot


@dataclass(frozen=True, slots=True)
class WorldModelPolicy:
    pose_max_age_ms: int = 250
    obstacle_max_age_ms: int = 500
    battery_max_age_ms: int = 1_000
    minimum_quality: float = 0.60


class WorldModel:
    """Builds immutable snapshots and explicitly marks stale/low-quality sources."""

    def __init__(self, policy: WorldModelPolicy | None = None) -> None:
        self.policy = policy or WorldModelPolicy()
        self._pose: Pose2D | None = None
        self._obstacles: dict[str, Obstacle] = {}
        self._battery_percent: float | None = None
        self._battery_timestamp_ms: int | None = None
        self._sequence = 0

    def update_pose(self, pose: Pose2D) -> None:
        if self._pose and pose.timestamp_ms < self._pose.timestamp_ms:
            raise ValueError("out-of-order pose update")
        self._pose = pose
        self._sequence += 1

    def update_obstacles(self, obstacles: tuple[Obstacle, ...]) -> None:
        for obstacle in obstacles:
            previous = self._obstacles.get(obstacle.obstacle_id)
            if previous and obstacle.timestamp_ms < previous.timestamp_ms:
                raise ValueError(f"out-of-order obstacle update: {obstacle.obstacle_id}")
            self._obstacles[obstacle.obstacle_id] = obstacle
        self._sequence += 1

    def update_battery(self, battery_percent: float, timestamp_ms: int) -> None:
        if not 0.0 <= battery_percent <= 100.0:
            raise ValueError("battery_percent must be in [0, 100]")
        if timestamp_ms < 0:
            raise ValueError("battery timestamp must be non-negative")
        if self._battery_timestamp_ms is not None and timestamp_ms < self._battery_timestamp_ms:
            raise ValueError("out-of-order battery update")
        self._battery_percent = float(battery_percent)
        self._battery_timestamp_ms = timestamp_ms
        self._sequence += 1

    def snapshot(self, now_ms: int) -> WorldSnapshot:
        if self._pose is None:
            raise RuntimeError("pose is unavailable")
        if self._battery_percent is None or self._battery_timestamp_ms is None:
            raise RuntimeError("battery state is unavailable")
        if now_ms < self._pose.timestamp_ms:
            raise ValueError("now_ms cannot predate pose")
        if now_ms < self._battery_timestamp_ms:
            raise ValueError("now_ms cannot predate battery state")

        stale: list[str] = []
        if now_ms - self._pose.timestamp_ms > self.policy.pose_max_age_ms:
            stale.append("pose")
        if self._pose.quality < self.policy.minimum_quality:
            stale.append("pose_quality")
        if now_ms - self._battery_timestamp_ms > self.policy.battery_max_age_ms:
            stale.append("battery")

        fresh_obstacles: list[Obstacle] = []
        for obstacle in sorted(self._obstacles.values(), key=lambda item: item.obstacle_id):
            if now_ms < obstacle.timestamp_ms:
                raise ValueError(f"obstacle timestamp is in the future: {obstacle.obstacle_id}")
            if now_ms - obstacle.timestamp_ms > self.policy.obstacle_max_age_ms:
                stale.append(f"obstacle:{obstacle.obstacle_id}")
            elif obstacle.confidence >= self.policy.minimum_quality:
                fresh_obstacles.append(obstacle)

        return WorldSnapshot(
            snapshot_id=str(uuid4()),
            created_at_ms=now_ms,
            pose=self._pose,
            obstacles=tuple(fresh_obstacles),
            battery_percent=self._battery_percent,
            battery_timestamp_ms=self._battery_timestamp_ms,
            source_sequence=self._sequence,
            stale_sources=tuple(stale),
        )
