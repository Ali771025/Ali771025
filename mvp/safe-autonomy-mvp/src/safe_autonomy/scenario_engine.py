from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path

from .flight_state_analyzer import FlightStateAnalyzer
from .mission_contracts import (
    FindingSeverity,
    FlightPhase,
    FlightSample,
    SafeRecommendation,
    ScenarioDefinition,
    ScenarioResult,
)
from .resources import resolve_resource


_SEVERITY_RANK = {
    FindingSeverity.INFO: 0,
    FindingSeverity.WARNING: 1,
    FindingSeverity.HIGH: 2,
    FindingSeverity.CRITICAL: 3,
}


def nominal_flight_sample() -> FlightSample:
    return FlightSample(
        timestamp_ms=1_000, host_monotonic_ms=1_000, armed=True, landed=False,
        reported_mode="MISSION", local_x_m=20.0, local_y_m=20.0,
        altitude_agl_m=60.0, terrain_clearance_m=45.0,
        ground_speed_mps=12.0, vertical_speed_mps=0.0,
        roll_deg=3.0, pitch_deg=2.0, battery_percent=80.0,
        gps_quality=0.95, estimator_healthy=True, link_quality=0.95,
        telemetry_age_ms=40, route_deviation_m=0.5, distance_to_goal_m=500.0,
        geofence_margin_m=100.0, obstacle_ttc_s=None,
        camera_healthy=True, tracker_healthy=True, landing_zone_clear=True,
        phase_elapsed_s=30.0, map_age_ms=1_000,
    )


class ScenarioEngine:
    def __init__(self, analyzer: FlightStateAnalyzer | None = None) -> None:
        self.analyzer = analyzer or FlightStateAnalyzer()

    @staticmethod
    def load(path: str | Path) -> tuple[ScenarioDefinition, ...]:
        payload = json.loads(resolve_resource(path, "safe_autonomy_config").read_text(encoding="utf-8"))
        return tuple(ScenarioDefinition(
            scenario_id=str(item["scenario_id"]), version=str(item.get("version", "1.0")),
            title=str(item["title"]), category=str(item["category"]),
            description=str(item["description"]), overrides=dict(item.get("overrides", {})),
            expected_recommendation=SafeRecommendation(item["expected_recommendation"]),
            minimum_severity=FindingSeverity(item["minimum_severity"]),
            enabled=bool(item.get("enabled", True)),
        ) for item in payload["scenarios"])

    def run(self, definition: ScenarioDefinition, now_ms: int | None = None) -> ScenarioResult:
        started = now_ms if now_ms is not None else time.time_ns() // 1_000_000
        overrides = dict(definition.overrides)
        previous_phase_raw = overrides.pop("previous_phase", None)
        previous_phase = FlightPhase(previous_phase_raw) if previous_phase_raw else None
        sample = replace(nominal_flight_sample(), **overrides)
        assessment = self.analyzer.analyze(sample, started + 1, previous_phase)
        action_ok = assessment.recommendation == definition.expected_recommendation
        severity_ok = _SEVERITY_RANK[assessment.highest_severity] >= _SEVERITY_RANK[definition.minimum_severity]
        failure = None
        if not action_ok:
            failure = f"expected {definition.expected_recommendation.value}, got {assessment.recommendation.value}"
        elif not severity_ok:
            failure = f"expected severity >= {definition.minimum_severity.value}, got {assessment.highest_severity.value}"
        return ScenarioResult(definition, assessment, action_ok and severity_ok, failure, started, started + 2)

    def run_all(self, definitions: tuple[ScenarioDefinition, ...], now_ms: int | None = None) -> tuple[ScenarioResult, ...]:
        base = now_ms if now_ms is not None else time.time_ns() // 1_000_000
        return tuple(self.run(definition, base + index * 10) for index, definition in enumerate(definitions) if definition.enabled)
