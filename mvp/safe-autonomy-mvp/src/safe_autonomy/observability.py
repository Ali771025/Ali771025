from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True, slots=True)
class MetricSnapshot:
    name: str
    count: int
    minimum_ms: float
    maximum_ms: float
    mean_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    budget_ms: float
    within_budget_ratio: float


class LatencyRegistry:
    """Small dependency-free latency registry suitable for SIL and API health."""

    def __init__(self, maximum_samples_per_metric: int = 4096) -> None:
        if maximum_samples_per_metric < 10:
            raise ValueError("maximum_samples_per_metric must be at least 10")
        self.maximum_samples = maximum_samples_per_metric
        self._values: dict[str, list[float]] = {}
        self._lock = RLock()

    def observe(self, name: str, latency_ms: float) -> None:
        if not name or latency_ms < 0:
            raise ValueError("invalid latency observation")
        with self._lock:
            values = self._values.setdefault(name, [])
            values.append(float(latency_ms))
            if len(values) > self.maximum_samples:
                del values[: len(values) - self.maximum_samples]

    def snapshot(self, name: str, budget_ms: float) -> MetricSnapshot:
        if budget_ms <= 0:
            raise ValueError("budget_ms must be positive")
        with self._lock:
            values = sorted(self._values.get(name, ()))
        if not values:
            return MetricSnapshot(name, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, budget_ms, 1.0)
        def percentile(ratio: float) -> float:
            return values[min(len(values) - 1, round((len(values) - 1) * ratio))]
        return MetricSnapshot(
            name, len(values), values[0], values[-1], sum(values) / len(values),
            percentile(0.50), percentile(0.95), percentile(0.99), budget_ms,
            sum(value <= budget_ms for value in values) / len(values),
        )
