from __future__ import annotations

import json
from dataclasses import asdict

from .assurance_contracts import (
    AssuranceReport,
    EnergyAssessment,
    RouteRevalidation,
    SystemReadiness,
    TemporalObservation,
)
from .database import Database
from .observability import MetricSnapshot


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_default)


def _json_default(value: object) -> object:
    try:
        return asdict(value)  # type: ignore[arg-type]
    except TypeError:
        if hasattr(value, "value"):
            return value.value  # type: ignore[union-attr]
        raise


class AssuranceRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def save_temporal(self, observation: TemporalObservation) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO temporal_observations(
                    observation_id, source, sequence_no, source_monotonic_ms,
                    received_monotonic_ms, verdict, age_ms, cross_source_skew_ms, reasons_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    observation.observation_id, observation.source, observation.sequence,
                    observation.source_monotonic_ms, observation.received_monotonic_ms,
                    observation.verdict.value, observation.age_ms,
                    observation.cross_source_skew_ms, _json(observation.reasons),
                ),
            )

    def save_readiness(self, readiness: SystemReadiness, connection=None) -> None:
        def _write(conn):
            conn.execute(
                """INSERT OR IGNORE INTO system_readiness_snapshots(
                    snapshot_id, state, score, gates_json, evaluated_monotonic_ms, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (readiness.snapshot_id, readiness.state.value, readiness.score, _json(readiness.gates), readiness.evaluated_monotonic_ms, readiness.schema_version),
            )
        if connection is not None:
            _write(connection)
        else:
            with self.database.transaction() as conn:
                _write(conn)

    def save_energy(self, assessment: EnergyAssessment, connection=None) -> None:
        def _write(conn):
            conn.execute(
                """INSERT OR IGNORE INTO energy_assessments(
                    assessment_id, feasible, estimated_energy_wh, available_energy_wh,
                    reserve_energy_wh, margin_wh, wind_penalty_ratio, gates_json, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    assessment.assessment_id, int(assessment.feasible), assessment.estimated_energy_wh,
                    assessment.available_energy_wh, assessment.reserve_energy_wh,
                    assessment.margin_wh, assessment.wind_penalty_ratio, _json(assessment.gates), assessment.schema_version,
                ),
            )
        if connection is not None:
            _write(connection)
        else:
            with self.database.transaction() as conn:
                _write(conn)

    def save_revalidation(self, assessment: RouteRevalidation) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO route_revalidations(
                    assessment_id, route_candidate_id, recommendation, cross_track_error_m,
                    progress_ratio, remaining_distance_m, corridor_risk, reasons_json,
                    evaluated_monotonic_ms, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    assessment.assessment_id, assessment.route_candidate_id, assessment.recommendation,
                    assessment.cross_track_error_m, assessment.progress_ratio,
                    assessment.remaining_distance_m, assessment.corridor_risk,
                    _json(assessment.reasons), assessment.evaluated_monotonic_ms, assessment.schema_version,
                ),
            )

    def save_report(self, report: AssuranceReport) -> None:
        # Persist readiness, energy, and the report itself in a single atomic transaction
        # to avoid orphaned readiness/energy rows when the report insert fails.
        with self.database.transaction() as connection:
            self.save_readiness(report.readiness, connection=connection)
            self.save_energy(report.energy, connection=connection)
            connection.execute(
                """INSERT INTO assurance_reports(
                    report_id, mission_id, overall_status, readiness_snapshot_id,
                    energy_assessment_id, gates_json, input_sha256, created_at_ms, schema_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    report.report_id, report.mission_id, report.overall_status.value,
                    report.readiness.snapshot_id, report.energy.assessment_id,
                    _json(report.gates), report.input_sha256, report.created_at_ms, report.schema_version,
                ),
            )

    def save_slo(self, snapshot: MetricSnapshot, created_at_ms: int) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                "INSERT INTO latency_slo_snapshots(metric_name, snapshot_json, created_at_ms) VALUES (?, ?, ?)",
                (snapshot.name, _json(asdict(snapshot)), created_at_ms),
            )
