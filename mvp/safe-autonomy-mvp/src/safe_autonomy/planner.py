from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from math import ceil, hypot, sqrt
from uuid import uuid4

from .contracts import Trajectory, TrajectoryPoint, Vector2, WorldSnapshot


GridCell = tuple[int, int]


@dataclass(frozen=True, slots=True)
class GridMap:
    min_x_m: float
    max_x_m: float
    min_y_m: float
    max_y_m: float
    resolution_m: float = 1.0

    def __post_init__(self) -> None:
        if self.min_x_m >= self.max_x_m or self.min_y_m >= self.max_y_m:
            raise ValueError("invalid grid bounds")
        if self.resolution_m <= 0:
            raise ValueError("resolution_m must be positive")

    def to_cell(self, point: Vector2) -> GridCell:
        return (
            round((point.x_m - self.min_x_m) / self.resolution_m),
            round((point.y_m - self.min_y_m) / self.resolution_m),
        )

    def to_point(self, cell: GridCell) -> Vector2:
        return Vector2(
            self.min_x_m + cell[0] * self.resolution_m,
            self.min_y_m + cell[1] * self.resolution_m,
        )

    @property
    def max_cell(self) -> GridCell:
        return self.to_cell(Vector2(self.max_x_m, self.max_y_m))

    def contains_cell(self, cell: GridCell) -> bool:
        max_x, max_y = self.max_cell
        return 0 <= cell[0] <= max_x and 0 <= cell[1] <= max_y


class PlanningError(RuntimeError):
    pass


class DeterministicAStarPlanner:
    """Deterministic 8-connected A*; never consumes free-form model output."""

    _MOVES: tuple[tuple[int, int, float], ...] = (
        (-1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0), (1, 0, 1.0),
        (-1, -1, sqrt(2)), (-1, 1, sqrt(2)), (1, -1, sqrt(2)), (1, 1, sqrt(2)),
    )

    def __init__(self, grid: GridMap, obstacle_margin_m: float = 1.0) -> None:
        self.grid = grid
        self.obstacle_margin_m = obstacle_margin_m

    def plan(
        self,
        request_id: str,
        world: WorldSnapshot,
        goal: Vector2,
        generated_at_ms: int,
        speed_mps: float = 2.0,
    ) -> Trajectory:
        if speed_mps <= 0:
            raise ValueError("speed_mps must be positive")
        start = self.grid.to_cell(world.pose.position)
        goal_cell = self.grid.to_cell(goal)
        if not self.grid.contains_cell(start) or not self.grid.contains_cell(goal_cell):
            raise PlanningError("start or goal is outside the grid")

        blocked = self._blocked_cells(world)
        if start in blocked or goal_cell in blocked:
            raise PlanningError("start or goal intersects an inflated obstacle")
        cells = self._a_star(start, goal_cell, blocked)
        points = self._parameterize(cells, speed_mps)
        return Trajectory(
            trajectory_id=str(uuid4()),
            request_id=request_id,
            world_snapshot_id=world.snapshot_id,
            generated_at_ms=generated_at_ms,
            points=points,
        )

    def _blocked_cells(self, world: WorldSnapshot) -> set[GridCell]:
        blocked: set[GridCell] = set()
        for obstacle in world.obstacles:
            uncertainty_m = sqrt(obstacle.position_variance_m2)
            radius_cells = ceil(
                (obstacle.radius_m + self.obstacle_margin_m + uncertainty_m)
                / self.grid.resolution_m
            )
            center = self.grid.to_cell(obstacle.position)
            for dx in range(-radius_cells, radius_cells + 1):
                for dy in range(-radius_cells, radius_cells + 1):
                    cell = (center[0] + dx, center[1] + dy)
                    if self.grid.contains_cell(cell) and hypot(dx, dy) <= radius_cells:
                        blocked.add(cell)
        return blocked

    def _a_star(self, start: GridCell, goal: GridCell, blocked: set[GridCell]) -> list[GridCell]:
        frontier: list[tuple[float, float, GridCell]] = [(0.0, 0.0, start)]
        parent: dict[GridCell, GridCell | None] = {start: None}
        cost: dict[GridCell, float] = {start: 0.0}

        while frontier:
            _, current_cost, current = heappop(frontier)
            if current == goal:
                break
            if current_cost > cost[current]:
                continue
            for dx, dy, movement_cost in self._MOVES:
                neighbour = (current[0] + dx, current[1] + dy)
                if not self.grid.contains_cell(neighbour) or neighbour in blocked:
                    continue
                candidate = cost[current] + movement_cost
                if candidate < cost.get(neighbour, float("inf")):
                    cost[neighbour] = candidate
                    parent[neighbour] = current
                    heuristic = hypot(goal[0] - neighbour[0], goal[1] - neighbour[1])
                    heappush(frontier, (candidate + heuristic, candidate, neighbour))

        if goal not in parent:
            raise PlanningError("no collision-free path exists")
        path: list[GridCell] = []
        node: GridCell | None = goal
        while node is not None:
            path.append(node)
            node = parent[node]
        return list(reversed(path))

    def _parameterize(self, cells: list[GridCell], speed_mps: float) -> tuple[TrajectoryPoint, ...]:
        elapsed_s = 0.0
        points: list[TrajectoryPoint] = []
        previous: Vector2 | None = None
        for cell in cells:
            point = self.grid.to_point(cell)
            if previous is not None:
                elapsed_s += hypot(point.x_m - previous.x_m, point.y_m - previous.y_m) / speed_mps
            points.append(TrajectoryPoint(point, elapsed_s, speed_mps))
            previous = point
        return tuple(points)

