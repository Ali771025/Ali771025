from __future__ import annotations

import json
from pathlib import Path

from .safety import Geofence, SafetyPolicy
from .world_model import WorldModelPolicy


def load_policies(path: str | Path) -> tuple[WorldModelPolicy, SafetyPolicy]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != "1.0":
        raise ValueError("unsupported policy schema_version")
    geofence = Geofence(**data["geofence"])
    world_policy = WorldModelPolicy(
        pose_max_age_ms=int(data["pose_max_age_ms"]),
        obstacle_max_age_ms=int(data["world_model_max_age_ms"]),
        battery_max_age_ms=int(data["battery_max_age_ms"]),
        minimum_quality=float(data["minimum_quality"]),
    )
    safety_policy = SafetyPolicy(
        world_model_max_age_ms=int(data["world_model_max_age_ms"]),
        minimum_battery_percent=float(data["minimum_battery_percent"]),
        maximum_speed_mps=float(data["maximum_speed_mps"]),
        maximum_acceleration_mps2=float(data["maximum_acceleration_mps2"]),
        minimum_obstacle_separation_m=float(data["minimum_obstacle_separation_m"]),
        allowed_control_authority=str(data["allowed_control_authority"]),
        geofence=geofence,
    )
    return world_policy, safety_policy
