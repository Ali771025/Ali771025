from __future__ import annotations

from dataclasses import replace
from math import ceil, exp, hypot

from .assurance_contracts import DynamicTrack
from .mission_contracts import MissionMap


class DynamicRiskOverlay:
    """Projects fresh tracked objects into a bounded, auditable risk layer.

    It never changes the source map in place. High-confidence near-term cells
    become occupied in the returned analysis copy; lower-confidence projections
    only increase risk.
    """

    def __init__(
        self,
        prediction_horizon_s: float = 8.0,
        prediction_step_s: float = 1.0,
        maximum_track_age_ms: int = 500,
        hard_block_confidence: float = 0.80,
        safety_margin_m: float = 2.0,
    ) -> None:
        if prediction_horizon_s <= 0 or prediction_step_s <= 0 or maximum_track_age_ms < 0:
            raise ValueError("invalid dynamic-risk policy")
        self.prediction_horizon_s = prediction_horizon_s
        self.prediction_step_s = prediction_step_s
        self.maximum_track_age_ms = maximum_track_age_ms
        self.hard_block_confidence = hard_block_confidence
        self.safety_margin_m = safety_margin_m

    def apply(self, mission_map: MissionMap, tracks: tuple[DynamicTrack, ...], now_monotonic_ms: int) -> MissionMap:
        occupancy = bytearray(mission_map.occupancy)
        risk = list(mission_map.risk)
        steps = max(1, ceil(self.prediction_horizon_s / self.prediction_step_s))
        for track in tracks:
            age_ms = now_monotonic_ms - track.observed_monotonic_ms
            if age_ms < 0 or age_ms > self.maximum_track_age_ms or track.confidence <= 0:
                continue
            age_s = age_ms / 1000.0
            for step in range(steps + 1):
                future_s = age_s + step * self.prediction_step_s
                x_m = track.x_m + track.velocity_x_mps * future_s
                y_m = track.y_m + track.velocity_y_mps * future_s
                center = mission_map.to_cell(x_m, y_m)
                radius_cells = ceil((track.radius_m + self.safety_margin_m) / mission_map.resolution_m)
                temporal_decay = exp(-step / max(1.0, steps / 2.0))
                for dx in range(-radius_cells, radius_cells + 1):
                    for dy in range(-radius_cells, radius_cells + 1):
                        cell = (center[0] + dx, center[1] + dy)
                        if not mission_map.contains(cell):
                            continue
                        distance_m = hypot(dx, dy) * mission_map.resolution_m
                        radius_m = track.radius_m + self.safety_margin_m
                        if distance_m > radius_m:
                            continue
                        spatial = max(0.0, 1.0 - distance_m / max(radius_m, 1e-9))
                        projected_risk = track.confidence * temporal_decay * (0.5 + 0.5 * spatial)
                        index = mission_map.index(cell)
                        risk[index] = max(risk[index], min(1.0, projected_risk))
                        if step <= 1 and track.confidence >= self.hard_block_confidence:
                            occupancy[index] = 1
        return replace(mission_map, occupancy=bytes(occupancy), risk=tuple(risk))
