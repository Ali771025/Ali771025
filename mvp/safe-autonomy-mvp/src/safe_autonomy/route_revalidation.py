from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from threading import RLock

from .mission_contracts import MissionMap, RouteCandidate
from .assurance_contracts import RouteRevalidation


@dataclass(frozen=True, slots=True)
class RevalidationPolicy:
    warning_cross_track_m: float = 5.0
    critical_cross_track_m: float = 15.0
    maximum_corridor_risk: float = 0.75
    corridor_radius_m: float = 3.0
    replan_cooldown_ms: int = 3000


class RouteRevalidator:
    """Monitors a validated route and emits bounded replan/HOLD recommendations."""

    def __init__(self, policy: RevalidationPolicy | None = None) -> None:
        self.policy = policy or RevalidationPolicy()
        self._last_replan_ms: int | None = None
        self._lock = RLock()

    def evaluate(
        self,
        mission_map: MissionMap,
        candidate: RouteCandidate,
        x_m: float,
        y_m: float,
        now_monotonic_ms: int,
    ) -> RouteRevalidation:
        if not candidate.points:
            raise ValueError("candidate has no route points")
        nearest_index, segment_fraction, cross_track, progress, remaining = self._progress(candidate, x_m, y_m)
        radius_cells = max(0, round(self.policy.corridor_radius_m / mission_map.resolution_m))
        maximum_risk = 0.0
        blocked = False
        corridor_cells: set[tuple[int, int]] = set()
        route_tail = candidate.points[nearest_index:]
        if len(route_tail) == 1:
            corridor_cells.add((route_tail[0].cell_x, route_tail[0].cell_y))
        for first, second in zip(route_tail, route_tail[1:]):
            corridor_cells.update(self._bresenham((first.cell_x, first.cell_y), (second.cell_x, second.cell_y)))
        for center_x, center_y in corridor_cells:
            for dx in range(-radius_cells, radius_cells + 1):
                for dy in range(-radius_cells, radius_cells + 1):
                    if hypot(dx, dy) > radius_cells:
                        continue
                    cell = (center_x + dx, center_y + dy)
                    if not mission_map.contains(cell):
                        continue
                    maximum_risk = max(maximum_risk, mission_map.risk_at(cell))
                    blocked = blocked or mission_map.occupancy_at(cell) == 1
        reasons: list[str] = []
        recommendation = "CONTINUE"
        # Synchronise cooldown state so concurrent evaluations cannot both trip REQUEST_REPLAN.
        with self._lock:
            last_replan = self._last_replan_ms
            if blocked:
                reasons.append("ROUTE_CORRIDOR_BLOCKED")
                recommendation = "HOLD"
            elif cross_track > self.policy.critical_cross_track_m:
                reasons.append("CROSS_TRACK_CRITICAL")
                recommendation = "HOLD"
            elif cross_track > self.policy.warning_cross_track_m or maximum_risk > self.policy.maximum_corridor_risk:
                reasons.append("CROSS_TRACK_WARNING" if cross_track > self.policy.warning_cross_track_m else "CORRIDOR_RISK_HIGH")
                recommendation = "REQUEST_REPLAN"
                if last_replan is not None and now_monotonic_ms - last_replan < self.policy.replan_cooldown_ms:
                    recommendation = "MONITOR"
                    reasons.append("REPLAN_COOLDOWN_ACTIVE")
                else:
                    self._last_replan_ms = now_monotonic_ms
        return RouteRevalidation(
            candidate.candidate_id, recommendation, cross_track, progress,
            remaining, maximum_risk, tuple(reasons), now_monotonic_ms,
        )

    @staticmethod
    def _progress(candidate: RouteCandidate, x_m: float, y_m: float) -> tuple[int, float, float, float, float]:
        if len(candidate.points) == 1:
            point = candidate.points[0]
            return 0, 0.0, hypot(x_m - point.x_m, y_m - point.y_m), 1.0, 0.0
        lengths = [
            hypot(second.x_m - first.x_m, second.y_m - first.y_m)
            for first, second in zip(candidate.points, candidate.points[1:])
        ]
        total = sum(lengths)
        best: tuple[float, int, float] | None = None
        distance_before = 0.0
        best_along = 0.0
        for index, (first, second, length) in enumerate(zip(candidate.points, candidate.points[1:], lengths)):
            if length <= 1e-9:
                fraction = 0.0
            else:
                fraction = max(0.0, min(1.0, ((x_m - first.x_m) * (second.x_m - first.x_m) + (y_m - first.y_m) * (second.y_m - first.y_m)) / (length * length)))
            projected_x = first.x_m + fraction * (second.x_m - first.x_m)
            projected_y = first.y_m + fraction * (second.y_m - first.y_m)
            distance = hypot(x_m - projected_x, y_m - projected_y)
            if best is None or distance < best[0]:
                best = (distance, index, fraction)
                best_along = distance_before + fraction * length
            distance_before += length
        assert best is not None
        progress = best_along / total if total > 1e-9 else 1.0
        return best[1], best[2], best[0], progress, max(0.0, total - best_along)

    @staticmethod
    def _bresenham(start: tuple[int, int], end: tuple[int, int]) -> tuple[tuple[int, int], ...]:
        x0, y0 = start
        x1, y1 = end
        dx, sx = abs(x1 - x0), 1 if x0 < x1 else -1
        dy, sy = -abs(y1 - y0), 1 if y0 < y1 else -1
        error = dx + dy
        cells: list[tuple[int, int]] = []
        while True:
            cells.append((x0, y0))
            if x0 == x1 and y0 == y1:
                return tuple(cells)
            doubled = 2 * error
            if doubled >= dy:
                error += dy
                x0 += sx
            if doubled <= dx:
                error += dx
                y0 += sy
