from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path

from .database import Database
from .flight_state_analyzer import FlightStateAnalyzer
from .map_ingestion import MapAnalyzer, MapUploadService
from .mission_contracts import (
    CoordinateSystem,
    FlightPhase,
    FlightSample,
    MapFormat,
    MissionMap,
    RoutePolicy,
    RouteRequest,
)
from .mission_repository import MissionAnalysisRepository
from .mission_route_planner import MultiCriteriaAStarPlanner
from .scenario_engine import ScenarioEngine


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def fixture_map() -> MissionMap:
    width, height = 60, 40
    occupancy = bytearray(width * height)
    risk = [0.0] * (width * height)
    for x in range(width):
        occupancy[x] = 1
        occupancy[(height - 1) * width + x] = 1
    for y in range(height):
        occupancy[y * width] = 1
        occupancy[y * width + width - 1] = 1
    for y in range(1, height - 1):
        if not (7 <= y <= 11 or 25 <= y <= 30):
            occupancy[y * width + 30] = 1
    for y in range(14, 23):
        for x in range(12, 25):
            risk[y * width + x] = 0.65
    payload = bytes(occupancy)
    return MissionMap(
        "fixture-map-v05", "fixture-grid", MapFormat.FIXTURE,
        hashlib.sha256(payload).hexdigest(), len(payload), CoordinateSystem.LOCAL_ENU,
        width, height, 2.0, 0.0, 0.0, payload, tuple(risk), None,
    )


def command_ingest(args) -> dict[str, object]:
    database = Database(args.database)
    database.migrate()
    try:
        mission_map = MapUploadService(args.maximum_cells).ingest(args.map)
        analysis = MapAnalyzer().analyze(mission_map)
        map_id = MissionAnalysisRepository(database).save_map(mission_map, analysis)
        return {"map_id": map_id, "analysis": asdict(analysis)}
    finally:
        database.close()


def command_plan(args) -> dict[str, object]:
    database = Database(args.database)
    database.migrate()
    repository = MissionAnalysisRepository(database)
    request = RouteRequest(
        args.map_id, args.start_x, args.start_y, args.goal_x, args.goal_y,
        args.start_altitude, args.cruise_altitude,
        RoutePolicy(
            obstacle_inflation_m=args.inflation,
            minimum_terrain_clearance_m=args.clearance,
            cruise_speed_mps=args.speed,
            requested_alternatives=args.alternatives,
        ),
    )
    repository.start_route(request)
    try:
        candidates = MultiCriteriaAStarPlanner(repository.load_map(args.map_id)).plan(request)
        repository.finish_route(request, candidates)
        return {
            "request_id": request.request_id,
            "candidates": [
                {
                    "candidate_id": item.candidate_id, "rank": item.rank_no,
                    "valid": item.valid, "length_m": round(item.length_m, 2),
                    "duration_s": round(item.estimated_duration_s, 2),
                    "mean_risk": round(item.mean_risk, 4),
                    "distinctness": round(item.distinctness, 4), "points": len(item.points),
                }
                for item in candidates
            ],
        }
    except Exception as exc:
        repository.fail_route(request.request_id, str(exc))
        raise
    finally:
        database.close()


def command_analyze_flight(args) -> dict[str, object]:
    payload = json.loads(Path(args.sample).read_text(encoding="utf-8"))
    sample = FlightSample(**payload)
    previous = FlightPhase(args.previous_phase) if args.previous_phase else None
    assessment = FlightStateAnalyzer().analyze(sample, int(time.time() * 1000), previous)
    database = Database(args.database)
    database.migrate()
    try:
        MissionAnalysisRepository(database).save_assessment(assessment)
    finally:
        database.close()
    return asdict(assessment)


def command_scenarios(args) -> dict[str, object]:
    definitions = ScenarioEngine.load(args.config)
    results = ScenarioEngine().run_all(definitions)
    database = Database(args.database)
    database.migrate()
    repository = MissionAnalysisRepository(database)
    try:
        for result in results:
            repository.save_scenario_result(result)
    finally:
        database.close()
    return {
        "total": len(results), "passed": sum(result.passed for result in results),
        "failed": [
            {"scenario_id": result.definition.scenario_id, "reason": result.failure_reason}
            for result in results if not result.passed
        ],
    }


def command_demo(args) -> dict[str, object]:
    database = Database(args.database)
    database.migrate()
    repository = MissionAnalysisRepository(database)
    mission_map = fixture_map()
    analysis = MapAnalyzer().analyze(mission_map)
    repository.save_map(mission_map, analysis, 1_000)
    request = RouteRequest(
        mission_map.map_id, 8.0, 8.0, 108.0, 68.0, 25.0, 60.0,
        RoutePolicy(obstacle_inflation_m=2.0, requested_alternatives=3),
        request_id="fixture-route-request-v05",
    )
    repository.start_route(request, 1_010)
    candidates = MultiCriteriaAStarPlanner(mission_map).plan(request)
    repository.finish_route(request, candidates, 1_020)
    results = ScenarioEngine().run_all(ScenarioEngine.load(args.config), 2_000)
    for result in results:
        repository.save_scenario_result(result)
    database.close()
    return {
        "map_id": mission_map.map_id, "map_status": analysis.status.value,
        "route_candidates": len(candidates), "scenario_total": len(results),
        "scenario_passed": sum(item.passed for item in results),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Mission map, route, flight-state and SIL scenario analysis")
    parser.add_argument("--database", default="artifacts/mission_dev_v0.6.sqlite3")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest-map")
    ingest.add_argument("--map", required=True)
    ingest.add_argument("--maximum-cells", type=int, default=4_000_000)
    ingest.set_defaults(handler=command_ingest)

    plan = subparsers.add_parser("plan-route")
    plan.add_argument("--map-id", required=True)
    plan.add_argument("--start-x", type=float, required=True)
    plan.add_argument("--start-y", type=float, required=True)
    plan.add_argument("--goal-x", type=float, required=True)
    plan.add_argument("--goal-y", type=float, required=True)
    plan.add_argument("--start-altitude", type=float, default=20.0)
    plan.add_argument("--cruise-altitude", type=float, default=60.0)
    plan.add_argument("--speed", type=float, default=12.0)
    plan.add_argument("--clearance", type=float, default=20.0)
    plan.add_argument("--inflation", type=float, default=2.0)
    plan.add_argument("--alternatives", type=int, default=3)
    plan.set_defaults(handler=command_plan)

    flight = subparsers.add_parser("analyze-flight")
    flight.add_argument("--sample", required=True, help="JSON FlightSample payload")
    flight.add_argument("--previous-phase", choices=[phase.value for phase in FlightPhase])
    flight.set_defaults(handler=command_analyze_flight)

    scenarios = subparsers.add_parser("run-scenarios")
    scenarios.add_argument("--config", default="config/flight_scenarios.json")
    scenarios.set_defaults(handler=command_scenarios)

    demo = subparsers.add_parser("demo")
    demo.add_argument("--config", default="config/flight_scenarios.json")
    demo.set_defaults(handler=command_demo)

    args = parser.parse_args()
    print(_json(args.handler(args)))


if __name__ == "__main__":
    main()
