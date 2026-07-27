from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict

from .assurance_contracts import ModuleHeartbeat
from .assurance_repository import AssuranceRepository
from .database import Database
from .energy_model import RouteEnergyEstimator
from .health_manager import HealthPolicy, SystemHealthManager
from .map_ingestion import MapAnalyzer, MapUploadService
from .mission_assurance import MissionAssuranceEngine
from .mission_contracts import RoutePolicy, RouteRequest
from .mission_repository import MissionAnalysisRepository
from .mission_route_planner import MultiCriteriaAStarPlanner
from .observability import LatencyRegistry
from .resources import resolve_resource
from .temporal_guard import TemporalGuard


def run_demo(database_path: str, map_path: str) -> dict[str, object]:
    database = Database(database_path)
    database.migrate()
    mission_repository = MissionAnalysisRepository(database)
    assurance_repository = AssuranceRepository(database)
    try:
        mission_map = MapUploadService().ingest(resolve_resource(map_path, "safe_autonomy_maps"))
        map_analysis = MapAnalyzer().analyze(mission_map)
        mission_repository.save_map(mission_map, map_analysis)
        request = RouteRequest(
            mission_map.map_id, 10, 10, 180, 125, 25, 60,
            RoutePolicy(requested_alternatives=3),
        )
        mission_repository.start_route(request, 1_000)
        started_ns = time.perf_counter_ns()
        candidates = MultiCriteriaAStarPlanner(mission_map).plan(request)
        route_latency_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
        mission_repository.finish_route(request, candidates, 2_000)

        temporal = TemporalGuard().observe("px4_vehicle_odometry", 1, 995, 1_000)
        assurance_repository.save_temporal(temporal)
        health = SystemHealthManager()
        for module_id in HealthPolicy().required_modules + HealthPolicy().optional_modules:
            health.record(ModuleHeartbeat(module_id, 1_000, "HEALTHY", 5.0))
        readiness = health.evaluate(1_050)
        energy = RouteEnergyEstimator().evaluate(candidates[0], 2_000, 90, 2)
        report = MissionAssuranceEngine().evaluate(
            "release-demo-v0.6", map_analysis, candidates[0], readiness, energy, 2_000,
        )
        assurance_repository.save_report(report)
        metrics = LatencyRegistry()
        metrics.observe("route_plan", route_latency_ms)
        slo = metrics.snapshot("route_plan", 5_000)
        assurance_repository.save_slo(slo, 2_000)
        return {
            "version": "0.6.0-dev1",
            "map_id": mission_map.map_id,
            "map_status": map_analysis.status.value,
            "route_candidates": len(candidates),
            "readiness": readiness.state.value,
            "energy_feasible": energy.feasible,
            "assurance": report.overall_status.value,
            "input_sha256": report.input_sha256,
            "route_plan_latency_ms": route_latency_ms,
            "control_authority": "NONE",
        }
    finally:
        database.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the v0.6 mission-assurance release demo")
    parser.add_argument("--database", default="artifacts/mission_dev_v0.6.sqlite3")
    parser.add_argument("--map", default="maps/sample_mission.geojson")
    args = parser.parse_args()
    print(json.dumps(run_demo(args.database, args.map), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
