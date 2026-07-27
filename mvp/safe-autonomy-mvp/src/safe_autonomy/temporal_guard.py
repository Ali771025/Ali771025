from __future__ import annotations

from dataclasses import dataclass

from .assurance_contracts import TemporalObservation, TemporalVerdict


@dataclass(frozen=True, slots=True)
class TemporalPolicy:
    maximum_age_ms: int = 250
    maximum_future_ms: int = 20
    maximum_cross_source_skew_ms: int = 100
    warning_sequence_gap: int = 5

    def __post_init__(self) -> None:
        if min(self.maximum_age_ms, self.maximum_future_ms, self.maximum_cross_source_skew_ms) < 0:
            raise ValueError("temporal limits must be non-negative")
        if self.warning_sequence_gap < 1:
            raise ValueError("warning_sequence_gap must be positive")


class TemporalGuard:
    """Fail-closed sequence/freshness guard for normalized monotonic clocks."""

    def __init__(self, policy: TemporalPolicy | None = None) -> None:
        self.policy = policy or TemporalPolicy()
        self._last_sequence: dict[str, int] = {}
        self._last_source_time: dict[str, int] = {}

    def observe(
        self,
        source: str,
        sequence: int,
        source_monotonic_ms: int,
        received_monotonic_ms: int,
    ) -> TemporalObservation:
        if not source or min(sequence, source_monotonic_ms, received_monotonic_ms) < 0:
            raise ValueError("invalid temporal observation")
        reasons: list[str] = []
        rejected = False
        age_ms = received_monotonic_ms - source_monotonic_ms
        previous_sequence = self._last_sequence.get(source)
        previous_time = self._last_source_time.get(source)
        if previous_sequence is not None and sequence <= previous_sequence:
            reasons.append("OUT_OF_ORDER_SEQUENCE")
            rejected = True
        if previous_time is not None and source_monotonic_ms < previous_time:
            reasons.append("CLOCK_REGRESSION")
            rejected = True
        if age_ms > self.policy.maximum_age_ms:
            reasons.append("STALE_SAMPLE")
            rejected = True
        if age_ms < -self.policy.maximum_future_ms:
            reasons.append("FUTURE_SAMPLE")
            rejected = True
        if previous_sequence is not None and sequence - previous_sequence > self.policy.warning_sequence_gap:
            reasons.append("SEQUENCE_GAP")

        peer_window_ms = self.policy.maximum_age_ms + self.policy.maximum_cross_source_skew_ms
        peer_times = [
            value for key, value in self._last_source_time.items()
            if key != source and abs(received_monotonic_ms - value) <= peer_window_ms
        ]
        skew = max((abs(source_monotonic_ms - value) for value in peer_times), default=None)
        if skew is not None and skew > self.policy.maximum_cross_source_skew_ms:
            reasons.append("CROSS_SOURCE_SKEW")

        if rejected:
            verdict = TemporalVerdict.REJECT
        elif reasons:
            verdict = TemporalVerdict.DEGRADED
        else:
            verdict = TemporalVerdict.ACCEPT
        if verdict != TemporalVerdict.REJECT:
            self._last_sequence[source] = sequence
            self._last_source_time[source] = source_monotonic_ms
        return TemporalObservation(
            source, sequence, source_monotonic_ms, received_monotonic_ms,
            verdict, age_ms, skew, tuple(reasons),
        )

    def reset_source(self, source: str) -> None:
        self._last_sequence.pop(source, None)
        self._last_source_time.pop(source, None)
