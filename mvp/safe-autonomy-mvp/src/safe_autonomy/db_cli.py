from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


TABLES = (
    "video_runs",
    "detections",
    "world_snapshots",
    "world_obstacles",
    "trajectories",
    "trajectory_points",
    "safety_decisions",
    "safety_gate_results",
    "audit_events",
    "telemetry_samples",
    "telemetry_frames",
    "telemetry_perception_objects",
    "knowledge_documents",
    "knowledge_chunks",
    "knowledge_nodes",
    "knowledge_edges",
    "rag_queries",
    "rag_evidence",
    "advisory_proposals",
    "camera_streams",
    "vision_frames",
    "vision_objects",
    "sensor_vision_sync",
    "module_health_events",
    "wiring_revisions",
    "mission_maps",
    "route_plan_requests",
    "route_candidates",
    "route_points",
    "flight_assessments",
    "flight_findings",
    "scenario_definitions",
    "scenario_runs",
    "scenario_events",
    "temporal_observations",
    "system_readiness_snapshots",
    "energy_assessments",
    "route_revalidations",
    "assurance_reports",
    "latency_slo_snapshots",
)


def inspect_database(path: str | Path) -> dict[str, object]:
    database_path = Path(path)
    if not database_path.is_file():
        raise FileNotFoundError(database_path)
    connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        counts = {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in TABLES}
        migrations = [dict(row) for row in connection.execute("SELECT * FROM schema_migrations ORDER BY version")]
        latest_runs = [
            dict(row)
            for row in connection.execute(
                """SELECT run_id, source_name, backend, model_version, status, started_at_ms,
                          completed_at_ms, configuration_json
                   FROM video_runs ORDER BY created_at_ms DESC LIMIT 10"""
            )
        ]
        latest_routes = [
            dict(row)
            for row in connection.execute(
                """SELECT request_id, map_id, status, created_at_ms, completed_at_ms, error_message
                   FROM route_plan_requests ORDER BY created_at_ms DESC LIMIT 10"""
            )
        ]
        scenario_summary = dict(connection.execute(
            """SELECT COUNT(*) AS total_runs,
                      COALESCE(SUM(passed), 0) AS passed_runs,
                      COALESCE(SUM(CASE WHEN passed=0 THEN 1 ELSE 0 END), 0) AS failed_runs
               FROM scenario_runs"""
        ).fetchone())
        return {
            "database": str(database_path),
            "integrity": integrity,
            "migrations": migrations,
            "counts": counts,
            "latest_video_runs": latest_runs,
            "latest_route_requests": latest_routes,
            "scenario_summary": scenario_summary,
        }
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only autonomy database summary")
    parser.add_argument("--database", default="artifacts/autonomy_dev.sqlite3")
    args = parser.parse_args()
    print(json.dumps(inspect_database(args.database), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
