from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from .contracts import GateResult, SafetyDecision, Trajectory, Verdict, WorldSnapshot


@dataclass(frozen=True, slots=True)
class Geofence:
    min_x_m: float
    max_x_m: float
    min_y_m: float
    max_y_m: float

    def contains(self, x_m: float, y_m: float) -> bool:
        return self.min_x_m <= x_m <= self.max_x_m and self.min_y_m <= y_m <= self.max_y_m


@dataclass(frozen=True, slots=True)
class SafetyPolicy:
    world_model_max_age_ms: int
    minimum_battery_percent: float
    maximum_speed_mps: float
    maximum_acceleration_mps2: float
    minimum_obstacle_separation_m: float
    allowed_control_authority: str
    geofence: Geofence


class SafetySupervisor:
    """Independent, fail-closed gate evaluator for candidate trajectories."""

    def __init__(self, policy: SafetyPolicy) -> None:
        self.policy = policy

    def evaluate(
        self,
        trajectory: Trajectory,
        world: WorldSnapshot,
        evaluated_at_ms: int,
    ) -> SafetyDecision:
        gates = (
            self._snapshot_identity(trajectory, world),
            self._freshness(world, evaluated_at_ms),
            self._source_health(world),
            self._authority(trajectory),
            self._energy(world),
            self._geofence(trajectory),
            self._dynamics(trajectory),
            self._collision(trajectory, world),
        )
        verdict = Verdict.PASS if all(gate.passed for gate in gates) else Verdict.REJECT
        return SafetyDecision(
            request_id=trajectory.request_id,
            trajectory_id=trajectory.trajectory_id,
            evaluated_at_ms=evaluated_at_ms,
            verdict=verdict,
            gates=gates,
        )

    def _snapshot_identity(self, trajectory: Trajectory, world: WorldSnapshot) -> GateResult:
        passed = trajectory.world_snapshot_id == world.snapshot_id
        return GateResult("snapshot_identity", passed, "snapshot matches" if passed else "snapshot mismatch")

    def _freshness(self, world: WorldSnapshot, now_ms: int) -> GateResult:
        age = now_ms - world.created_at_ms
        passed = 0 <= age <= self.policy.world_model_max_age_ms
        return GateResult("freshness", passed, "fresh world model" if passed else "stale world model", age, self.policy.world_model_max_age_ms)

    def _source_health(self, world: WorldSnapshot) -> GateResult:
        passed = not world.stale_sources
        return GateResult("source_health", passed, "sources healthy" if passed else "stale or low-quality source", world.stale_sources, ())

    def _authority(self, trajectory: Trajectory) -> GateResult:
        passed = trajectory.control_authority == self.policy.allowed_control_authority
        return GateResult("control_authority", passed, "authority accepted" if passed else "unknown control authority", trajectory.control_authority, self.policy.allowed_control_authority)

    def _energy(self, world: WorldSnapshot) -> GateResult:
        passed = world.battery_percent >= self.policy.minimum_battery_percent
        return GateResult("energy", passed, "energy margin accepted" if passed else "battery below policy", world.battery_percent, self.policy.minimum_battery_percent)

    def _geofence(self, trajectory: Trajectory) -> GateResult:
        invalid = [index for index, point in enumerate(trajectory.points) if not self.policy.geofence.contains(point.position.x_m, point.position.y_m)]
        passed = not invalid
        return GateResult("geofence", passed, "inside geofence" if passed else "trajectory exits geofence", invalid, "all points inside")

    def _dynamics(self, trajectory: Trajectory) -> GateResult:
        speeds = [point.speed_mps for point in trajectory.points]
        max_speed = max(speeds)
        accelerations: list[float] = []
        for previous, current in zip(trajectory.points, trajectory.points[1:]):
            dt = current.time_from_start_s - previous.time_from_start_s
            accelerations.append(abs(current.speed_mps - previous.speed_mps) / dt)
        max_acceleration = max(accelerations, default=0.0)
        passed = max_speed <= self.policy.maximum_speed_mps and max_acceleration <= self.policy.maximum_acceleration_mps2
        return GateResult(
            "dynamics",
            passed,
            "dynamics accepted" if passed else "trajectory exceeds dynamics limits",
            {"max_speed_mps": max_speed, "max_acceleration_mps2": max_acceleration},
            {"maximum_speed_mps": self.policy.maximum_speed_mps, "maximum_acceleration_mps2": self.policy.maximum_acceleration_mps2},
        )

    def _collision(self, trajectory: Trajectory, world: WorldSnapshot) -> GateResult:
        minimum = float("inf")
        collision = False
        for point in trajectory.points:
            for obstacle in world.obstacles:
                distance = hypot(point.position.x_m - obstacle.position.x_m, point.position.y_m - obstacle.position.y_m) - obstacle.radius_m
                minimum = min(minimum, distance)
                if distance < self.policy.minimum_obstacle_separation_m:
                    collision = True
        observed = None if minimum == float("inf") else minimum
        return GateResult("collision", not collision, "separation accepted" if not collision else "minimum separation violated", observed, self.policy.minimum_obstacle_separation_m)

