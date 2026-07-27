from __future__ import annotations

import argparse
import os
import tempfile
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import asdict, replace
from pathlib import Path

from .assurance_contracts import DynamicTrack, ModuleHeartbeat
from .assurance_repository import AssuranceRepository
from .database import Database
from .dynamic_risk import DynamicRiskOverlay
from .energy_model import RouteEnergyEstimator
from .flight_state_analyzer import FlightStateAnalyzer
from .health_manager import SystemHealthManager
from .map_ingestion import MapAnalyzer, MapUploadService
from .mission_assurance import MissionAssuranceEngine
from .mission_contracts import (
    FlightPhase, FlightSample, RouteCandidate, RoutePoint3D, RoutePolicy, RouteRequest,
)
from .mission_repository import MissionAnalysisRepository
from .mission_route_planner import MultiCriteriaAStarPlanner
from .observability import LatencyRegistry
from .route_revalidation import RouteRevalidator
from .scenario_engine import ScenarioEngine
from .temporal_guard import TemporalGuard


def create_app(
    database_path: str = "artifacts/mission_dev_v0.6.sqlite3",
    scenario_config: str = "config/flight_scenarios.json",
    api_key: str | None = None,
    allowed_origins: str | None = None,
):
    try:
        from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.security import APIKeyHeader
    except ImportError as exc:
        raise RuntimeError("Install the mission API extra: pip install -e '.[mission-api]'") from exc
    globals()["UploadFile"] = UploadFile

    database = Database(database_path)
    database.migrate()
    repository = MissionAnalysisRepository(database)
    assurance_repository = AssuranceRepository(database)
    temporal_guard = TemporalGuard()
    health_manager = SystemHealthManager()
    revalidator = RouteRevalidator()
    latency = LatencyRegistry()

    resolved_api_key = api_key if api_key is not None else os.environ.get("SAFE_AUTONOMY_API_KEY", "")
    origins = [
        item.strip() for item in (allowed_origins or os.environ.get("SAFE_AUTONOMY_CORS_ORIGINS", "")).split(",")
        if item.strip()
    ]

    # Simple sliding-window rate limiter: 60 requests/minute per client IP.
    RATE_LIMIT_MAX = 60
    RATE_LIMIT_WINDOW_S = 60.0
    rate_state: dict[str, deque[float]] = defaultdict(deque)

    @asynccontextmanager
    async def lifespan(_app):
        try:
            yield
        finally:
            database.close()

    app = FastAPI(title="Safe Autonomy Mission Analysis API", version="0.6.0-dev1", lifespan=lifespan)

    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["content-type", "x-api-key"],
        )

    def _check_rate_limit(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = rate_state[client]
        while window and now - window[0] > RATE_LIMIT_WINDOW_S:
            window.popleft()
        if len(window) >= RATE_LIMIT_MAX:
            raise HTTPException(429, "rate limit exceeded")
        window.append(now)

    api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

    def require_api_key(key: str | None = Depends(api_key_scheme)) -> None:
        # If no API key is configured (development default), all requests are allowed.
        # When SAFE_AUTONOMY_API_KEY is set, the header MUST match.
        if not resolved_api_key:
            return
        if not key or key != resolved_api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing API key")

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"status": "HEALTHY", "control_authority": "NONE", "version": "0.6.0-dev1", "schema_version": "2.0"}

    @app.middleware("http")
    async def _security_and_rate_limit(request: Request, call_next):
        # Apply rate limit to all non-health endpoints when a key is configured
        # (health checks are used by orchestrators and must stay lightweight).
        if resolved_api_key and not request.url.path.startswith("/health"):
            _check_rate_limit(request)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.post("/api/v1/maps/upload", dependencies=[Depends(require_api_key)])
    async def upload_map(
        file: UploadFile = File(...),
        resolution_m: float | None = None,
        origin_x_m: float | None = None,
        origin_y_m: float | None = None,
    ) -> dict[str, object]:
        suffix = Path(file.filename or "upload").suffix.lower()
        if suffix not in {".json", ".geojson", ".pgm", ".tif", ".tiff"}:
            raise HTTPException(415, "unsupported map format")
        content = await file.read(64 * 1024 * 1024 + 1)
        if len(content) > 64 * 1024 * 1024:
            raise HTTPException(413, "map upload exceeds 64 MiB")
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
                handle.write(content)
                temporary_path = Path(handle.name)
            mission_map = MapUploadService().ingest(temporary_path)
            mission_map = replace(
                mission_map,
                source_name=Path(file.filename or "upload").name,
                resolution_m=resolution_m if suffix == ".pgm" and resolution_m is not None else mission_map.resolution_m,
                origin_x_m=origin_x_m if suffix == ".pgm" and origin_x_m is not None else mission_map.origin_x_m,
                origin_y_m=origin_y_m if suffix == ".pgm" and origin_y_m is not None else mission_map.origin_y_m,
            )
            analysis = MapAnalyzer().analyze(mission_map)
            map_id = repository.save_map(mission_map, analysis)
            return {"map_id": map_id, "analysis": asdict(analysis)}
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @app.post("/api/v1/routes/plan", dependencies=[Depends(require_api_key)])
    def plan_route(payload: dict) -> dict[str, object]:
        started_ns = time.perf_counter_ns()
        try:
            policy = RoutePolicy(**payload.get("policy", {}))
            request = RouteRequest(
                str(payload["map_id"]), float(payload["start_x_m"]), float(payload["start_y_m"]),
                float(payload["goal_x_m"]), float(payload["goal_y_m"]),
                float(payload.get("start_altitude_m", 20.0)), float(payload.get("cruise_altitude_m", 60.0)),
                policy,
            )
            repository.start_route(request)
            candidates = MultiCriteriaAStarPlanner(repository.load_map(request.map_id)).plan(request)
            repository.finish_route(request, candidates)
            return {"request_id": request.request_id, "candidates": [asdict(item) for item in candidates]}
        except (KeyError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc
        except Exception as exc:
            if "request" in locals():
                repository.fail_route(request.request_id, str(exc))
            raise HTTPException(409, str(exc)) from exc
        finally:
            latency.observe("route_plan", (time.perf_counter_ns() - started_ns) / 1_000_000)

    @app.post("/api/v1/flight/analyze", dependencies=[Depends(require_api_key)])
    def analyze_flight(payload: dict) -> dict[str, object]:
        try:
            body = dict(payload)
            previous_raw = body.pop("previous_phase", None)
            sample = FlightSample(**body)
            assessment = FlightStateAnalyzer().analyze(
                sample, int(time.time() * 1000), FlightPhase(previous_raw) if previous_raw else None,
            )
            repository.save_assessment(assessment)
            return asdict(assessment)
        except (TypeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/v1/scenarios/run", dependencies=[Depends(require_api_key)])
    def run_scenarios() -> dict[str, object]:
        results = ScenarioEngine().run_all(ScenarioEngine.load(scenario_config))
        for result in results:
            repository.save_scenario_result(result)
        return {"total": len(results), "passed": sum(result.passed for result in results), "failed": [result.failure_reason for result in results if not result.passed]}

    @app.post("/api/v2/time/observe", dependencies=[Depends(require_api_key)])
    def observe_time(payload: dict) -> dict[str, object]:
        try:
            result = temporal_guard.observe(
                str(payload["source"]), int(payload["sequence"]),
                int(payload["source_monotonic_ms"]), int(payload["received_monotonic_ms"]),
            )
            assurance_repository.save_temporal(result)
            return asdict(result)
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/v2/health/heartbeat", dependencies=[Depends(require_api_key)])
    def record_heartbeat(payload: dict) -> dict[str, object]:
        try:
            heartbeat = ModuleHeartbeat(**payload)
            health_manager.record(heartbeat)
            return {"accepted": True, "module_id": heartbeat.module_id}
        except (TypeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/v2/health/readiness", dependencies=[Depends(require_api_key)])
    def get_readiness(now_monotonic_ms: int) -> dict[str, object]:
        try:
            readiness = health_manager.evaluate(now_monotonic_ms)
            assurance_repository.save_readiness(readiness)
            return asdict(readiness)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/v2/routes/energy", dependencies=[Depends(require_api_key)])
    def assess_energy(payload: dict) -> dict[str, object]:
        try:
            assessment = RouteEnergyEstimator().evaluate(
                _route_candidate(payload["candidate"]), float(payload["battery_capacity_wh"]),
                float(payload["battery_percent"]), float(payload.get("headwind_mps", 0.0)),
            )
            assurance_repository.save_energy(assessment)
            return asdict(assessment)
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/v2/routes/revalidate", dependencies=[Depends(require_api_key)])
    def revalidate_route(payload: dict) -> dict[str, object]:
        try:
            mission_map = repository.load_map(str(payload["map_id"]))
            tracks = tuple(DynamicTrack(**item) for item in payload.get("dynamic_tracks", ()))
            if tracks:
                mission_map = DynamicRiskOverlay().apply(mission_map, tracks, int(payload["now_monotonic_ms"]))
            assessment = revalidator.evaluate(
                mission_map, _route_candidate(payload["candidate"]),
                float(payload["x_m"]), float(payload["y_m"]), int(payload["now_monotonic_ms"]),
            )
            assurance_repository.save_revalidation(assessment)
            return asdict(assessment)
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/api/v2/assurance/evaluate", dependencies=[Depends(require_api_key)])
    def evaluate_assurance(payload: dict) -> dict[str, object]:
        try:
            mission_map = repository.load_map(str(payload["map_id"]))
            route = _route_candidate(payload["candidate"])
            readiness = health_manager.evaluate(int(payload["now_monotonic_ms"]))
            energy = RouteEnergyEstimator().evaluate(
                route, float(payload["battery_capacity_wh"]), float(payload["battery_percent"]),
                float(payload.get("headwind_mps", 0.0)),
            )
            report = MissionAssuranceEngine().evaluate(
                str(payload["mission_id"]), MapAnalyzer().analyze(mission_map), route,
                readiness, energy, int(payload.get("created_at_ms", time.time() * 1000)),
            )
            assurance_repository.save_report(report)
            return asdict(report)
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/api/v2/metrics/latency/{metric_name}", dependencies=[Depends(require_api_key)])
    def get_latency(metric_name: str, budget_ms: float = 100.0) -> dict[str, object]:
        try:
            snapshot = latency.snapshot(metric_name, budget_ms)
            assurance_repository.save_slo(snapshot, int(time.time() * 1000))
            return asdict(snapshot)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Mission analysis development API")
    parser.add_argument("--database", default="artifacts/mission_dev_v0.6.sqlite3")
    parser.add_argument("--scenarios", default="config/flight_scenarios.json")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    args = parser.parse_args()
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("Install the mission API extra: pip install -e '.[mission-api]'") from exc
    uvicorn.run(create_app(args.database, args.scenarios), host=args.host, port=args.port)


def _route_candidate(payload: dict) -> RouteCandidate:
    """Strict adapter for API JSON; unknown command/control fields are rejected."""
    forbidden = {"vehicle_command", "trajectory_setpoint", "actuator", "waypoint_command"}
    if forbidden & set(payload):
        raise ValueError("control/actuator fields are forbidden in analysis API")
    points = tuple(RoutePoint3D(**point) for point in payload["points"])
    return RouteCandidate(
        request_id=str(payload["request_id"]), rank_no=int(payload["rank_no"]),
        total_cost=float(payload["total_cost"]), length_m=float(payload["length_m"]),
        estimated_duration_s=float(payload["estimated_duration_s"]), mean_risk=float(payload["mean_risk"]),
        minimum_clearance_m=None if payload.get("minimum_clearance_m") is None else float(payload["minimum_clearance_m"]),
        distinctness=float(payload["distinctness"]), points=points,
        validation_reasons=tuple(str(item) for item in payload.get("validation_reasons", ())),
        candidate_id=str(payload.get("candidate_id") or "api-candidate"),
    )


if __name__ == "__main__":
    main()
