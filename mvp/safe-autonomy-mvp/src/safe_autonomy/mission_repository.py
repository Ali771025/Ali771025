from __future__ import annotations

import json
import sys
import time
import zlib
from array import array
from dataclasses import asdict

from .database import Database
from .mission_contracts import (
    CoordinateSystem,
    FlightAssessment,
    MapAnalysis,
    MapFormat,
    MissionMap,
    RouteCandidate,
    RouteRequest,
    ScenarioDefinition,
    ScenarioResult,
)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _pack_floats(values: tuple[float, ...] | None) -> bytes | None:
    if values is None:
        return None
    data = array("d", values)
    if sys.byteorder != "little":
        data.byteswap()
    return zlib.compress(data.tobytes(), level=6)


def _unpack_floats(payload: bytes | None, count: int) -> tuple[float, ...] | None:
    if payload is None:
        return None
    data = array("d")
    data.frombytes(zlib.decompress(payload))
    if sys.byteorder != "little":
        data.byteswap()
    if len(data) != count:
        raise ValueError("stored map layer has an invalid length")
    return tuple(float(value) for value in data)


class MissionAnalysisRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def save_map(self, mission_map: MissionMap, analysis: MapAnalysis, created_at_ms: int | None = None) -> str:
        with self.database.transaction() as connection:
            existing = connection.execute(
                """SELECT map_id FROM mission_maps
                   WHERE source_sha256=? AND resolution_m=? AND origin_x_m=? AND origin_y_m=?""",
                (
                    mission_map.source_sha256, mission_map.resolution_m,
                    mission_map.origin_x_m, mission_map.origin_y_m,
                ),
            ).fetchone()
            if existing is not None:
                persisted_id = str(existing["map_id"])
            else:
                connection.execute(
                    """INSERT INTO mission_maps(
                        map_id, source_name, source_format, source_sha256, source_size_bytes,
                        coordinate_system, width_cells, height_cells, resolution_m,
                        origin_x_m, origin_y_m, occupancy_blob, risk_blob, elevation_blob,
                        analysis_json, status, created_at_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        mission_map.map_id, mission_map.source_name, mission_map.source_format.value,
                        mission_map.source_sha256, mission_map.source_size_bytes,
                        mission_map.coordinate_system.value, mission_map.width_cells,
                        mission_map.height_cells, mission_map.resolution_m,
                        mission_map.origin_x_m, mission_map.origin_y_m,
                        zlib.compress(mission_map.occupancy, level=6), _pack_floats(mission_map.risk),
                        _pack_floats(mission_map.elevation_m), _json(asdict(analysis)), analysis.status.value,
                        created_at_ms if created_at_ms is not None else time.time_ns() // 1_000_000,
                    ),
                )
                persisted_id = mission_map.map_id
        return persisted_id

    def load_map(self, map_id: str) -> MissionMap:
        row = self.database.connection.execute("SELECT * FROM mission_maps WHERE map_id=?", (map_id,)).fetchone()
        if row is None:
            raise KeyError(map_id)
        count = int(row["width_cells"]) * int(row["height_cells"])
        occupancy = zlib.decompress(row["occupancy_blob"])
        if len(occupancy) != count:
            raise ValueError("stored occupancy layer has an invalid length")
        risk = _unpack_floats(row["risk_blob"], count)
        assert risk is not None
        return MissionMap(
            str(row["map_id"]), str(row["source_name"]), MapFormat(row["source_format"]),
            str(row["source_sha256"]), int(row["source_size_bytes"]),
            CoordinateSystem(row["coordinate_system"]), int(row["width_cells"]),
            int(row["height_cells"]), float(row["resolution_m"]),
            float(row["origin_x_m"]), float(row["origin_y_m"]), occupancy, risk,
            _unpack_floats(row["elevation_blob"], count),
        )

    def start_route(self, request: RouteRequest, created_at_ms: int | None = None) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO route_plan_requests(
                    request_id, map_id, start_x_m, start_y_m, goal_x_m, goal_y_m,
                    start_altitude_m, cruise_altitude_m, policy_json, status, created_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'RUNNING', ?)""",
                (
                    request.request_id, request.map_id, request.start_x_m, request.start_y_m,
                    request.goal_x_m, request.goal_y_m, request.start_altitude_m,
                    request.cruise_altitude_m, _json(asdict(request.policy)),
                    created_at_ms if created_at_ms is not None else time.time_ns() // 1_000_000,
                ),
            )

    def finish_route(
        self,
        request: RouteRequest,
        candidates: tuple[RouteCandidate, ...],
        completed_at_ms: int | None = None,
    ) -> None:
        completed = completed_at_ms if completed_at_ms is not None else time.time_ns() // 1_000_000
        with self.database.transaction() as connection:
            for candidate in candidates:
                connection.execute(
                    """INSERT INTO route_candidates(
                        candidate_id, request_id, rank_no, total_cost, length_m,
                        estimated_duration_s, mean_risk, minimum_clearance_m,
                        distinctness, validation_status, validation_reasons_json, created_at_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        candidate.candidate_id, request.request_id, candidate.rank_no,
                        candidate.total_cost, candidate.length_m, candidate.estimated_duration_s,
                        candidate.mean_risk, candidate.minimum_clearance_m, candidate.distinctness,
                        "VALID" if candidate.valid else "REJECTED", _json(candidate.validation_reasons), completed,
                    ),
                )
                connection.executemany(
                    """INSERT INTO route_points(
                        candidate_id, sequence_no, cell_x, cell_y, x_m, y_m,
                        altitude_m, time_from_start_s, cumulative_cost
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [
                        (
                            candidate.candidate_id, index, point.cell_x, point.cell_y,
                            point.x_m, point.y_m, point.altitude_m,
                            point.time_from_start_s, point.cumulative_cost,
                        )
                        for index, point in enumerate(candidate.points)
                    ],
                )
            connection.execute(
                "UPDATE route_plan_requests SET status='SUCCEEDED', completed_at_ms=? WHERE request_id=?",
                (completed, request.request_id),
            )

    def fail_route(self, request_id: str, error: str, completed_at_ms: int | None = None) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """UPDATE route_plan_requests SET status='FAILED', error_message=?, completed_at_ms=?
                   WHERE request_id=?""",
                (error, completed_at_ms if completed_at_ms is not None else time.time_ns() // 1_000_000, request_id),
            )

    def save_assessment(self, assessment: FlightAssessment) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO flight_assessments(
                    assessment_id, telemetry_frame_id, sample_json, inferred_phase,
                    previous_phase, transition_valid, health_score, highest_severity,
                    recommendation, created_at_ms, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    assessment.assessment_id, assessment.sample.telemetry_frame_id,
                    _json(asdict(assessment.sample)), assessment.inferred_phase.value,
                    assessment.previous_phase.value if assessment.previous_phase else None,
                    int(assessment.transition_valid), assessment.health_score,
                    assessment.highest_severity.value, assessment.recommendation.value,
                    assessment.created_at_ms, assessment.schema_version,
                ),
            )
            connection.executemany(
                """INSERT INTO flight_findings(
                    assessment_id, sequence_no, code, severity, message, observed_json, limit_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        assessment.assessment_id, index, finding.code, finding.severity.value,
                        finding.message, _json(finding.observed), _json(finding.limit),
                    )
                    for index, finding in enumerate(assessment.findings)
                ],
            )

    def save_scenario_definition(self, definition: ScenarioDefinition) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO scenario_definitions(
                    scenario_id, version, title, category, description,
                    input_json, expected_json, enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    definition.scenario_id, definition.version, definition.title,
                    definition.category, definition.description, _json(definition.overrides),
                    _json({"recommendation": definition.expected_recommendation.value, "minimum_severity": definition.minimum_severity.value}),
                    int(definition.enabled),
                ),
            )

    def save_scenario_result(self, result: ScenarioResult) -> None:
        self.save_scenario_definition(result.definition)
        self.save_assessment(result.assessment)
        actual = {
            "recommendation": result.assessment.recommendation.value,
            "severity": result.assessment.highest_severity.value,
            "phase": result.assessment.inferred_phase.value,
            "finding_codes": [finding.code for finding in result.assessment.findings],
        }
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO scenario_runs(
                    run_id, scenario_id, scenario_version, started_at_ms, completed_at_ms,
                    passed, actual_json, failure_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.run_id, result.definition.scenario_id, result.definition.version, result.started_at_ms,
                    result.completed_at_ms, int(result.passed), _json(actual), result.failure_reason,
                ),
            )
            connection.executemany(
                """INSERT INTO scenario_events(run_id, sequence_no, event_type, payload_json, timestamp_ms)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    (result.run_id, 0, "FAULT_INJECTED", _json(result.definition.overrides), result.started_at_ms),
                    (result.run_id, 1, "ASSESSMENT_COMPLETED", _json(actual), result.completed_at_ms),
                ),
            )
