from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from .assurance_contracts import AssuranceReport, EnergyAssessment, GateResult, GateStatus, SystemReadiness
from .mission_contracts import MapAnalysis, MapStatus, RouteCandidate


class MissionAssuranceEngine:
    """Combines independent deterministic gates into an immutable proposal report."""

    def evaluate(
        self,
        mission_id: str,
        map_analysis: MapAnalysis,
        route: RouteCandidate,
        readiness: SystemReadiness,
        energy: EnergyAssessment,
        created_at_ms: int,
    ) -> AssuranceReport:
        if not mission_id:
            raise ValueError("mission_id is required")
        gates = [
            GateResult(
                "MAP_VALIDITY",
                GateStatus.PASS if map_analysis.status == MapStatus.VALID else GateStatus.WARN if map_analysis.status == MapStatus.DEGRADED else GateStatus.FAIL,
                f"map status is {map_analysis.status.value}", {"status": map_analysis.status.value, "warnings": map_analysis.warnings}, {"required": "VALID"},
            ),
            GateResult(
                "ROUTE_VALIDATION", GateStatus.PASS if route.valid else GateStatus.FAIL,
                "route passed independent validation" if route.valid else "route validation rejected candidate",
                {"candidate_id": route.candidate_id, "reasons": route.validation_reasons}, {"required_reasons": []},
            ),
            GateResult(
                "SYSTEM_READINESS", GateStatus.PASS if readiness.state.value == "READY" else GateStatus.WARN if readiness.state.value == "DEGRADED" else GateStatus.FAIL,
                f"system readiness is {readiness.state.value}", {"score": readiness.score}, {"minimum_state": "READY"},
            ),
            GateResult(
                "ENERGY_FEASIBILITY", _energy_gate_status(energy),
                "energy reserve is feasible" if energy.feasible and _energy_gate_status(energy) == GateStatus.PASS else "energy estimate has an envelope warning" if energy.feasible else "energy reserve is insufficient",
                {"margin_wh": energy.margin_wh}, {"minimum_margin_wh": 0.0},
            ),
        ]
        overall = GateStatus.FAIL if any(g.status == GateStatus.FAIL for g in gates) else GateStatus.WARN if any(g.status == GateStatus.WARN for g in gates) else GateStatus.PASS
        canonical_input = _without_generated_ids(
            {"mission_id": mission_id, "map": asdict(map_analysis), "route": asdict(route), "readiness": asdict(readiness), "energy": asdict(energy)}
        )
        canonical = json.dumps(
            canonical_input,
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return AssuranceReport(mission_id, overall, readiness, energy, tuple(gates), digest, created_at_ms)


def _without_generated_ids(value: object) -> object:
    """Remove transport identities so the assurance hash describes content."""
    generated = {"candidate_id", "request_id", "snapshot_id", "assessment_id", "report_id", "observation_id"}
    if isinstance(value, dict):
        return {key: _without_generated_ids(item) for key, item in value.items() if key not in generated}
    if isinstance(value, (list, tuple)):
        return [_without_generated_ids(item) for item in value]
    return value


def _energy_gate_status(energy: EnergyAssessment) -> GateStatus:
    if not energy.feasible or any(gate.status == GateStatus.FAIL for gate in energy.gates):
        return GateStatus.FAIL
    if any(gate.status == GateStatus.WARN for gate in energy.gates):
        return GateStatus.WARN
    return GateStatus.PASS
