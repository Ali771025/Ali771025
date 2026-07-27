from __future__ import annotations

from dataclasses import replace
from heapq import heappop, heappush
from math import ceil, hypot, sqrt

from .mission_contracts import (
    GridCell,
    MissionMap,
    RouteCandidate,
    RoutePoint3D,
    RouteRequest,
)
from .planner import PlanningError


State = tuple[int, int, int]


class MultiCriteriaAStarPlanner:
    """Deterministic 2.5D A*: occupancy is hard; risk/elevation/turning are bounded costs."""

    _MOVES: tuple[tuple[int, int, float], ...] = (
        (-1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0), (1, 0, 1.0),
        (-1, -1, sqrt(2)), (-1, 1, sqrt(2)), (1, -1, sqrt(2)), (1, 1, sqrt(2)),
    )

    def __init__(self, mission_map: MissionMap) -> None:
        self.map = mission_map

    def plan(self, request: RouteRequest) -> tuple[RouteCandidate, ...]:
        if request.map_id != self.map.map_id:
            raise PlanningError("route request references a different map")
        start = self.map.to_cell(request.start_x_m, request.start_y_m)
        goal = self.map.to_cell(request.goal_x_m, request.goal_y_m)
        if not self.map.contains(start) or not self.map.contains(goal):
            raise PlanningError("start or goal is outside the uploaded map")
        blocked = self._inflated_blocked(request)
        if start in blocked or goal in blocked:
            raise PlanningError("start or goal intersects an inflated obstacle/unknown cell")
        start_elevation = self.map.elevation_at(start)
        if (
            start_elevation is not None
            and request.start_altitude_m < start_elevation + request.policy.minimum_terrain_clearance_m
        ):
            raise PlanningError("start altitude violates minimum terrain clearance")

        accepted_cells: list[list[GridCell]] = []
        candidates: list[RouteCandidate] = []
        penalty: dict[GridCell, float] = {}
        maximum_attempts = max(1, request.policy.requested_alternatives * 6)
        for attempt in range(maximum_attempts):
            cells, _ = self._search(start, goal, blocked, request, penalty)
            distinctness = 1.0 if not accepted_cells else min(self._distinctness(cells, prior) for prior in accepted_cells)
            if not accepted_cells or distinctness >= request.policy.minimum_distinctness:
                accepted_cells.append(cells)
                candidates.append(self._candidate(request, cells, len(candidates) + 1, distinctness))
                if len(candidates) >= request.policy.requested_alternatives:
                    break
            factor = 2.5 + attempt * 1.5
            for prior in accepted_cells or [cells]:
                for cell in prior[2:-2]:
                    penalty[cell] = penalty.get(cell, 0.0) + factor * self.map.resolution_m
        if not candidates:
            raise PlanningError("no valid route candidate exists")
        ordered = sorted(candidates, key=lambda item: (item.total_cost, item.rank_no))
        return tuple(replace(candidate, rank_no=index + 1) for index, candidate in enumerate(ordered))

    def _inflated_blocked(self, request: RouteRequest) -> set[GridCell]:
        blocked: set[GridCell] = set()
        sources: list[GridCell] = []
        for index, value in enumerate(self.map.occupancy):
            if value == 1 or (value == 2 and request.policy.unknown_is_blocked):
                sources.append((index % self.map.width_cells, index // self.map.width_cells))
        radius = ceil(request.policy.obstacle_inflation_m / self.map.resolution_m)
        for source_x, source_y in sources:
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    cell = (source_x + dx, source_y + dy)
                    if self.map.contains(cell) and hypot(dx, dy) <= radius:
                        blocked.add(cell)
        return blocked

    def _search(
        self,
        start: GridCell,
        goal: GridCell,
        blocked: set[GridCell],
        request: RouteRequest,
        diversity_penalty: dict[GridCell, float],
    ) -> tuple[list[GridCell], float]:
        start_state: State = (start[0], start[1], -1)
        frontier: list[tuple[float, float, State]] = [(0.0, 0.0, start_state)]
        parent: dict[State, State | None] = {start_state: None}
        cost: dict[State, float] = {start_state: 0.0}
        goal_state: State | None = None
        while frontier:
            _, current_cost, current = heappop(frontier)
            if current_cost > cost[current]:
                continue
            if (current[0], current[1]) == goal:
                goal_state = current
                break
            for direction, (dx, dy, move_scale) in enumerate(self._MOVES):
                neighbour = (current[0] + dx, current[1] + dy)
                if not self.map.contains(neighbour) or neighbour in blocked:
                    continue
                if dx and dy and ((current[0] + dx, current[1]) in blocked or (current[0], current[1] + dy) in blocked):
                    continue
                distance_m = move_scale * self.map.resolution_m
                risk_cost = distance_m * request.policy.risk_weight * self.map.risk_at(neighbour)
                elevation_cost = self._altitude_delta((current[0], current[1]), neighbour, request) * request.policy.elevation_weight
                turn_cost = 0.0 if current[2] in {-1, direction} else request.policy.turn_penalty
                candidate_cost = current_cost + distance_m + risk_cost + elevation_cost + turn_cost + diversity_penalty.get(neighbour, 0.0)
                next_state = (neighbour[0], neighbour[1], direction)
                if candidate_cost < cost.get(next_state, float("inf")):
                    cost[next_state] = candidate_cost
                    parent[next_state] = current
                    heuristic = hypot(goal[0] - neighbour[0], goal[1] - neighbour[1]) * self.map.resolution_m
                    heappush(frontier, (candidate_cost + heuristic, candidate_cost, next_state))
        if goal_state is None:
            raise PlanningError("no collision-free A* path exists")
        states: list[State] = []
        node: State | None = goal_state
        while node is not None:
            states.append(node)
            node = parent[node]
        return [(state[0], state[1]) for state in reversed(states)], cost[goal_state]

    def _altitude_delta(self, first: GridCell, second: GridCell, request: RouteRequest) -> float:
        return abs(self._required_altitude(first, request) - self._required_altitude(second, request))

    def _required_altitude(self, cell: GridCell, request: RouteRequest) -> float:
        elevation = self.map.elevation_at(cell)
        if elevation is None:
            return request.cruise_altitude_m
        return max(request.cruise_altitude_m, elevation + request.policy.minimum_terrain_clearance_m)

    def _smooth(self, cells: list[GridCell], blocked: set[GridCell]) -> list[GridCell]:
        if len(cells) <= 2:
            return cells
        smoothed = [cells[0]]
        anchor = 0
        while anchor < len(cells) - 1:
            candidate = len(cells) - 1
            while candidate > anchor + 1 and not self._line_clear(cells[anchor], cells[candidate], blocked):
                candidate -= 1
            smoothed.append(cells[candidate])
            anchor = candidate
        return smoothed

    def _line_clear(self, start: GridCell, end: GridCell, blocked: set[GridCell]) -> bool:
        for cell in self._bresenham(start, end):
            if cell in blocked or not self.map.contains(cell):
                return False
        return True

    @staticmethod
    def _bresenham(start: GridCell, end: GridCell) -> list[GridCell]:
        x0, y0 = start
        x1, y1 = end
        dx, sx = abs(x1 - x0), 1 if x0 < x1 else -1
        dy, sy = -abs(y1 - y0), 1 if y0 < y1 else -1
        error = dx + dy
        cells: list[GridCell] = []
        while True:
            cells.append((x0, y0))
            if x0 == x1 and y0 == y1:
                break
            doubled = 2 * error
            if doubled >= dy:
                error += dy
                x0 += sx
            if doubled <= dx:
                error += dx
                y0 += sy
        return cells

    def _candidate(self, request: RouteRequest, cells: list[GridCell], rank: int, distinctness: float) -> RouteCandidate:
        points: list[RoutePoint3D] = []
        elapsed = 0.0
        length = 0.0
        cumulative_cost = 0.0
        risks: list[float] = []
        clearances: list[float] = []
        previous_xy: tuple[float, float] | None = None
        previous_altitude = request.start_altitude_m
        previous_cell: GridCell | None = None
        previous_direction: tuple[int, int] | None = None
        for index, cell in enumerate(cells):
            x_m, y_m = self.map.to_point(cell)
            terrain = self.map.elevation_at(cell)
            required_altitude = (terrain + request.policy.minimum_terrain_clearance_m) if terrain is not None else request.cruise_altitude_m
            altitude = max(request.cruise_altitude_m, required_altitude)
            if index == 0:
                altitude = max(request.start_altitude_m, required_altitude)
            if previous_xy is not None:
                horizontal = hypot(x_m - previous_xy[0], y_m - previous_xy[1])
                vertical = altitude - previous_altitude
                horizontal_time = horizontal / request.policy.cruise_speed_mps
                vertical_time = (
                    vertical / request.policy.maximum_climb_rate_mps if vertical >= 0
                    else abs(vertical) / request.policy.maximum_descent_rate_mps
                )
                elapsed += max(horizontal_time, vertical_time)
                length += hypot(horizontal, vertical)
            risk = self.map.risk_at(cell)
            risks.append(risk)
            if previous_xy is not None and previous_cell is not None:
                direction = (cell[0] - previous_cell[0], cell[1] - previous_cell[1])
                turn_cost = request.policy.turn_penalty if previous_direction is not None and direction != previous_direction else 0.0
                cumulative_cost += (
                    horizontal * (1.0 + request.policy.risk_weight * risk)
                    + abs(altitude - previous_altitude) * request.policy.elevation_weight
                    + turn_cost
                )
                previous_direction = direction
            if terrain is not None:
                clearances.append(altitude - terrain)
            points.append(RoutePoint3D(cell[0], cell[1], x_m, y_m, altitude, elapsed, cumulative_cost))
            previous_xy, previous_altitude, previous_cell = (x_m, y_m), altitude, cell
        mean_risk = sum(risks) / len(risks)
        minimum_clearance = min(clearances) if clearances else None
        reasons = self.validate(request, tuple(points))
        return RouteCandidate(
            request.request_id, rank, cumulative_cost, length, elapsed, mean_risk,
            minimum_clearance, distinctness, tuple(points), reasons,
        )

    def validate(self, request: RouteRequest, points: tuple[RoutePoint3D, ...]) -> tuple[str, ...]:
        reasons: list[str] = []
        if len(points) < 2:
            reasons.append("route contains fewer than two points")
            return tuple(reasons)
        for point in points:
            cell = (point.cell_x, point.cell_y)
            if not self.map.contains(cell) or self.map.occupancy_at(cell) != 0:
                reasons.append(f"point intersects non-free cell: {cell}")
                continue
            terrain = self.map.elevation_at(cell)
            if terrain is not None and point.altitude_m - terrain < request.policy.minimum_terrain_clearance_m - 1e-6:
                reasons.append(f"terrain clearance violation at {cell}")
        for previous, current in zip(points, points[1:]):
            delta_t = current.time_from_start_s - previous.time_from_start_s
            if delta_t <= 0:
                reasons.append("route time is not strictly increasing")
                continue
            vertical_rate = (current.altitude_m - previous.altitude_m) / delta_t
            if vertical_rate > request.policy.maximum_climb_rate_mps + 1e-6:
                reasons.append("maximum climb rate exceeded")
            if vertical_rate < -request.policy.maximum_descent_rate_mps - 1e-6:
                reasons.append("maximum descent rate exceeded")
        return tuple(sorted(set(reasons)))

    @staticmethod
    def _distinctness(first: list[GridCell], second: list[GridCell]) -> float:
        first_cells, second_cells = set(first[1:-1]), set(second[1:-1])
        if not first_cells or not second_cells:
            return 0.0
        overlap = len(first_cells & second_cells) / min(len(first_cells), len(second_cells))
        return max(0.0, min(1.0, 1.0 - overlap))
