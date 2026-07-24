from __future__ import annotations
import time
from collections import deque
from typing import Deque

class FPSCounter:
    def __init__(self, window: int = 30):
        self.window = window
        self.timestamps: Deque[float] = deque(maxlen=window)
        self._last = None

    def tick(self):
        now = time.time()
        self.timestamps.append(now)
        self._last = now

    def get_fps(self) -> float:
        if len(self.timestamps) < 2:
            return 0.0
        dt = self.timestamps[-1] - self.timestamps[0]
        if dt <= 0:
            return 0.0
        return (len(self.timestamps)-1)/dt

class LatencyTracker:
    def __init__(self, window: int = 100):
        self.latencies: Deque[float] = deque(maxlen=window)

    def add(self, ms: float):
        self.latencies.append(ms)

    def avg(self) -> float:
        if not self.latencies:
            return 0.0
        return sum(self.latencies)/len(self.latencies)

    def p50(self) -> float:
        return self._percentile(0.5)

    def p95(self) -> float:
        return self._percentile(0.95)

    def p99(self) -> float:
        return self._percentile(0.99)

    def _percentile(self, q: float) -> float:
        if not self.latencies:
            return 0.0
        s = sorted(self.latencies)
        idx = int(q*(len(s)-1))
        return s[idx]
