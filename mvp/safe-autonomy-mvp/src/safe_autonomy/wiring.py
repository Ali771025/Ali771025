from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .resources import resolve_resource


REQUIRED_MODULES = {
    "camera_ingest", "yolo_tracker", "overlay", "stream_publisher",
    "px4_telemetry", "timestamp_sync", "world_model", "decision_engine",
    "hybrid_rag", "transformer_advisory", "evidence_gate", "audit_database",
    "operator_gateway", "map_ingest", "map_analyzer", "route_planner",
    "route_validator", "flight_state_analyzer", "scenario_engine",
    "temporal_guard", "dynamic_risk_overlay", "route_revalidator",
    "energy_estimator", "health_manager", "mission_assurance", "observability",
}


def load_wiring(path: str | Path) -> dict[str, object]:
    return json.loads(resolve_resource(path, "safe_autonomy_config").read_text(encoding="utf-8"))


def validate_wiring(configuration: dict[str, object]) -> tuple[str, ...]:
    problems: list[str] = []
    modules_list = configuration.get("modules")
    connections = configuration.get("connections")
    if not isinstance(modules_list, list) or not isinstance(connections, list):
        return ("modules and connections must be arrays",)
    modules: dict[str, dict[str, object]] = {}
    forbidden_contracts = set(configuration.get("forbidden_contracts", ()))
    for item in modules_list:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            problems.append("every module requires a string id")
            continue
        module_id = str(item["id"])
        if module_id in modules:
            problems.append(f"duplicate module: {module_id}")
        modules[module_id] = item
        for direction in ("inputs", "outputs"):
            ports = item.get(direction, {})
            if isinstance(ports, dict):
                for port, contract in ports.items():
                    if contract in forbidden_contracts:
                        problems.append(f"forbidden contract on {module_id}.{port}: {contract}")
    for missing in sorted(REQUIRED_MODULES - modules.keys()):
        problems.append(f"missing required module: {missing}")

    destination_ports: set[str] = set()
    adjacency: dict[str, set[str]] = {module_id: set() for module_id in modules}
    for index, connection in enumerate(connections):
        if not isinstance(connection, dict):
            problems.append(f"connection[{index}] must be an object")
            continue
        source = str(connection.get("source", ""))
        target = str(connection.get("target", ""))
        if "." not in source or "." not in target:
            problems.append(f"connection[{index}] endpoints must be module.port")
            continue
        source_id, source_port = source.split(".", 1)
        target_id, target_port = target.split(".", 1)
        if source_id not in modules or target_id not in modules:
            problems.append(f"connection[{index}] references an unknown module")
            continue
        outputs = modules[source_id].get("outputs", {})
        inputs = modules[target_id].get("inputs", {})
        source_contract = outputs.get(source_port) if isinstance(outputs, dict) else None
        target_contract = inputs.get(target_port) if isinstance(inputs, dict) else None
        declared_contract = connection.get("contract")
        if declared_contract in forbidden_contracts:
            problems.append(f"connection[{index}] uses forbidden contract: {declared_contract}")
        if source_contract is None:
            problems.append(f"unknown output port: {source}")
        if target_contract is None:
            problems.append(f"unknown input port: {target}")
        if source_contract != target_contract or declared_contract != source_contract:
            problems.append(f"contract mismatch: {source} -> {target}")
        if target in destination_ports:
            problems.append(f"multiple producers for input: {target}")
        destination_ports.add(target)
        adjacency[source_id].add(target_id)
        if connection.get("queue_policy") not in {"drop_oldest", "latest_only", "durable", "request_reply"}:
            problems.append(f"connection[{index}] has invalid queue_policy")

    advisory_sources = {mid for mid, item in modules.items() if item.get("authority") == "advisory"}
    prohibited_targets = {mid for mid, item in modules.items() if item.get("authority") in {"actuator", "flight_control"}}
    for source in advisory_sources:
        reachable = _reachable(source, adjacency)
        for target in sorted(reachable & prohibited_targets):
            problems.append(f"forbidden advisory-to-control path: {source} -> {target}")

    for item in modules.values():
        if item.get("authority") in {"actuator", "flight_control"}:
            problems.append(f"flight output module is outside this developer build: {item['id']}")
    return tuple(sorted(set(problems)))


def _reachable(start: str, adjacency: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    pending = list(adjacency.get(start, ()))
    while pending:
        node = pending.pop()
        if node in seen:
            continue
        seen.add(node)
        pending.extend(adjacency.get(node, ()))
    return seen


def wiring_checksum(configuration: dict[str, object]) -> str:
    canonical = json.dumps(configuration, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate safe-autonomy module wiring")
    parser.add_argument("--config", default="config/system.wiring.json")
    args = parser.parse_args()
    configuration = load_wiring(args.config)
    problems = validate_wiring(configuration)
    result = {
        "valid": not problems,
        "schema_version": configuration.get("schema_version"),
        "checksum_sha256": wiring_checksum(configuration),
        "problems": problems,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if not problems else 2)


if __name__ == "__main__":
    main()
