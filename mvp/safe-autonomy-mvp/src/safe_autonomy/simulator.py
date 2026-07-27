from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

from .audit import CompositeAuditLog, DatabaseAuditLog, JsonlAuditLog
from .config import load_policies
from .contracts import Intent, MissionState, Obstacle, Pose2D, Vector2, Verdict
from .mission import MissionManager
from .database import AutonomyRepository, Database
from .planner import DeterministicAStarPlanner, GridMap
from .safety import SafetySupervisor
from .world_model import WorldModel


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_scenario(
    name: str,
    now_ms: int = 10_000,
    database_path: str | Path = ":memory:",
    audit_jsonl_path: str | Path | None = None,
) -> dict:
    """Run a deterministic SIL scenario without sharing mutable test state.

    Earlier releases always opened ``artifacts/autonomy_dev.sqlite3``.  A ZIP
    cannot safely carry SQLite WAL state, so a copied development database
    could be malformed.  Library callers and tests now use an isolated in-memory
    database; the CLI opts into a durable path explicitly.
    """
    world_policy, safety_policy = load_policies(PROJECT_ROOT / "config" / "policy.json")
    world_model = WorldModel(world_policy)
    sensor_timestamp = now_ms if name != "stale_state" else now_ms - 1_000
    world_model.update_pose(Pose2D(Vector2(1.0, 1.0), 0.0, sensor_timestamp, 0.95, 0.04))
    world_model.update_obstacles((
        Obstacle("obs-1", Vector2(8.0, 8.0), 1.0, 0.95, sensor_timestamp, 0.09),
    ))
    world_model.update_battery(10.0 if name == "low_battery" else 80.0, sensor_timestamp)
    world = world_model.snapshot(now_ms)

    planner = DeterministicAStarPlanner(GridMap(0.0, 20.0, 0.0, 20.0), obstacle_margin_m=1.0)
    safety = SafetySupervisor(safety_policy)
    database = Database(database_path)
    database.migrate()
    repository = AutonomyRepository(database)
    audit_sinks = [DatabaseAuditLog(repository)]
    if audit_jsonl_path is not None:
        audit_sinks.insert(0, JsonlAuditLog(audit_jsonl_path))
    audit = CompositeAuditLog(*audit_sinks)
    manager = MissionManager(planner, safety, audit, repository)
    decision = manager.handle_intent(Intent.START_MISSION, f"scenario-{name}", world, now_ms, Vector2(15.0, 15.0))

    if name == "authority_conflict" and decision is not None:
        trajectory = planner.plan("scenario-authority_conflict", world, Vector2(15.0, 15.0), now_ms)
        trajectory = replace(trajectory, control_authority="UNKNOWN_PUBLISHER")
        repository.save_trajectory(trajectory)
        decision = safety.evaluate(trajectory, world, now_ms)
        repository.save_safety_decision(decision)
        if decision.verdict == Verdict.REJECT:
            manager.state = MissionState.HOLD

    result = {
        "scenario": name,
        "mission_state": manager.state.value,
        "world_stale_sources": world.stale_sources,
        "decision": asdict(decision) if decision else None,
    }
    database.close()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run safety-first SIL scenarios")
    parser.add_argument("--scenario", choices=("nominal", "stale_state", "low_battery", "authority_conflict"), default="nominal")
    parser.add_argument("--database", default="artifacts/autonomy_dev_v0.6.sqlite3")
    parser.add_argument("--audit-jsonl", default="artifacts/audit_v0.6.jsonl")
    args = parser.parse_args()
    print(json.dumps(run_scenario(args.scenario, database_path=args.database, audit_jsonl_path=args.audit_jsonl), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
