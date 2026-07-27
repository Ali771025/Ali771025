from __future__ import annotations

from dataclasses import asdict

from .audit import AuditSink
from .contracts import AuditEvent, Intent, MissionState, SafetyDecision, Vector2, Verdict, WorldSnapshot
from .planner import DeterministicAStarPlanner, PlanningError
from .safety import SafetySupervisor


class MissionManager:
    """Owns mission state. Advisory systems can submit only a typed Intent."""

    def __init__(self, planner: DeterministicAStarPlanner, safety: SafetySupervisor, audit: AuditSink, repository=None) -> None:
        self.planner = planner
        self.safety = safety
        self.audit = audit
        self.repository = repository
        self.state = MissionState.IDLE

    def handle_intent(
        self,
        intent: Intent,
        request_id: str,
        world: WorldSnapshot,
        now_ms: int,
        goal: Vector2 | None = None,
    ) -> SafetyDecision | None:
        self._audit("INTENT_RECEIVED", now_ms, request_id, {"intent": intent.value, "state": self.state.value})
        if intent in {Intent.HOLD, Intent.ABSTAIN}:
            self.state = MissionState.HOLD
            self._audit("MISSION_STATE", now_ms, request_id, {"state": self.state.value})
            return None
        if intent == Intent.RETURN:
            self.state = MissionState.RETURN
            self._audit("MISSION_STATE", now_ms, request_id, {"state": self.state.value})
            return None
        if intent == Intent.LAND:
            self.state = MissionState.LAND
            self._audit("MISSION_STATE", now_ms, request_id, {"state": self.state.value})
            return None
        if intent == Intent.ABORT_MISSION:
            self.state = MissionState.ABORTED
            self._audit("MISSION_STATE", now_ms, request_id, {"state": self.state.value})
            return None
        if intent not in {Intent.START_MISSION, Intent.REQUEST_REROUTE}:
            raise ValueError(f"unsupported intent: {intent}")
        if goal is None:
            raise ValueError("goal is required for planning intents")

        self.state = MissionState.PLANNING
        if self.repository is not None:
            self.repository.save_world_snapshot(world)
        try:
            trajectory = self.planner.plan(request_id, world, goal, generated_at_ms=now_ms)
        except PlanningError as exc:
            self.state = MissionState.HOLD
            self._audit("PLANNING_REJECTED", now_ms, request_id, {"reason": str(exc), "state": self.state.value})
            return None

        decision = self.safety.evaluate(trajectory, world, evaluated_at_ms=now_ms)
        if self.repository is not None:
            self.repository.save_trajectory(trajectory)
            self.repository.save_safety_decision(decision)
        self.state = MissionState.READY if decision.verdict == Verdict.PASS else MissionState.HOLD
        self._audit(
            "SAFETY_DECISION",
            now_ms,
            request_id,
            {"state": self.state.value, "decision": asdict(decision)},
        )
        return decision

    def _audit(self, event_type: str, now_ms: int, correlation_id: str, payload: dict) -> None:
        self.audit.append(AuditEvent(event_type, now_ms, correlation_id, payload))
