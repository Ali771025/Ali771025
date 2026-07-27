from __future__ import annotations

from dataclasses import dataclass

from .assurance_contracts import (
    GateResult,
    GateStatus,
    ModuleHeartbeat,
    ReadinessState,
    SystemReadiness,
)


@dataclass(frozen=True, slots=True)
class HealthPolicy:
    required_modules: tuple[str, ...] = (
        "px4_telemetry", "timestamp_sync", "world_model", "decision_engine",
        "map_ingest", "route_planner", "route_validator", "audit_database",
    )
    optional_modules: tuple[str, ...] = (
        "camera_ingest", "yolo_tracker", "hybrid_rag", "transformer_advisory",
    )
    maximum_heartbeat_age_ms: int = 1500
    maximum_latency_ms: float = 250.0
    maximum_queue_depth: int = 8


class SystemHealthManager:
    def __init__(self, policy: HealthPolicy | None = None) -> None:
        self.policy = policy or HealthPolicy()
        self._heartbeats: dict[str, ModuleHeartbeat] = {}

    def record(self, heartbeat: ModuleHeartbeat) -> None:
        previous = self._heartbeats.get(heartbeat.module_id)
        if previous and heartbeat.observed_monotonic_ms < previous.observed_monotonic_ms:
            raise ValueError("heartbeat clock regression")
        self._heartbeats[heartbeat.module_id] = heartbeat

    def _evict_stale(self, now_monotonic_ms: int) -> None:
        """Drop heartbeat entries older than 10x the freshness window to bound memory."""
        horizon = now_monotonic_ms - 10 * self.policy.maximum_heartbeat_age_ms
        stale_ids = [
            module_id for module_id, hb in self._heartbeats.items()
            if hb.observed_monotonic_ms < horizon
        ]
        for module_id in stale_ids:
            self._heartbeats.pop(module_id, None)

    def evaluate(self, now_monotonic_ms: int) -> SystemReadiness:
        if now_monotonic_ms < 0:
            raise ValueError("now_monotonic_ms must be non-negative")
        self._evict_stale(now_monotonic_ms)
        gates: list[GateResult] = []
        for module_id in self.policy.required_modules + self.policy.optional_modules:
            required = module_id in self.policy.required_modules
            heartbeat = self._heartbeats.get(module_id)
            if heartbeat is None:
                gates.append(GateResult(
                    f"MODULE_{module_id}", GateStatus.FAIL if required else GateStatus.WARN,
                    "required heartbeat missing" if required else "optional heartbeat missing",
                    {"present": False}, {"required": required},
                ))
                continue
            age = now_monotonic_ms - heartbeat.observed_monotonic_ms
            if age < 0 or age > self.policy.maximum_heartbeat_age_ms:
                status = GateStatus.FAIL if required else GateStatus.WARN
                reason = "heartbeat stale or from the future"
            elif heartbeat.status.upper() not in {"HEALTHY", "OK", "READY"}:
                status = GateStatus.FAIL if required else GateStatus.WARN
                reason = "module reports unhealthy status"
            elif heartbeat.latency_ms > self.policy.maximum_latency_ms or heartbeat.queue_depth > self.policy.maximum_queue_depth:
                status = GateStatus.WARN
                reason = "latency or queue pressure exceeds warning limit"
            else:
                status = GateStatus.PASS
                reason = "heartbeat is fresh and healthy"
            gates.append(GateResult(
                f"MODULE_{module_id}", status, reason,
                {"age_ms": age, "status": heartbeat.status, "latency_ms": heartbeat.latency_ms, "queue_depth": heartbeat.queue_depth},
                {"max_age_ms": self.policy.maximum_heartbeat_age_ms, "max_latency_ms": self.policy.maximum_latency_ms, "max_queue_depth": self.policy.maximum_queue_depth},
            ))
        failed_required = any(gate.status == GateStatus.FAIL and gate.gate.removeprefix("MODULE_") in self.policy.required_modules for gate in gates)
        has_warning = any(gate.status != GateStatus.PASS for gate in gates)
        state = ReadinessState.NOT_READY if failed_required else ReadinessState.DEGRADED if has_warning else ReadinessState.READY
        score = max(0.0, 100.0 - sum(25 if gate.status == GateStatus.FAIL else 7 if gate.status == GateStatus.WARN else 0 for gate in gates))
        return SystemReadiness(state, score, tuple(gates), now_monotonic_ms)
