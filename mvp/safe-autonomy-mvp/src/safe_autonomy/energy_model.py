from __future__ import annotations

from dataclasses import dataclass

from .assurance_contracts import EnergyAssessment, GateResult, GateStatus
from .mission_contracts import RouteCandidate


@dataclass(frozen=True, slots=True)
class EnergyPolicy:
    cruise_power_w: float = 650.0
    climb_energy_wh_per_m: float = 0.08
    reserve_ratio: float = 0.25
    avionics_power_w: float = 55.0
    maximum_headwind_mps: float = 12.0

    def __post_init__(self) -> None:
        if min(self.cruise_power_w, self.climb_energy_wh_per_m, self.avionics_power_w) < 0:
            raise ValueError("energy coefficients must be non-negative")
        if not 0 < self.reserve_ratio < 1 or self.maximum_headwind_mps <= 0:
            raise ValueError("invalid energy reserve/wind policy")


class RouteEnergyEstimator:
    """Conservative route-level energy feasibility check, not a motor model."""

    def __init__(self, policy: EnergyPolicy | None = None) -> None:
        self.policy = policy or EnergyPolicy()

    def evaluate(
        self,
        candidate: RouteCandidate,
        battery_capacity_wh: float,
        battery_percent: float,
        headwind_mps: float = 0.0,
    ) -> EnergyAssessment:
        if battery_capacity_wh <= 0 or not 0 <= battery_percent <= 100:
            raise ValueError("invalid battery capacity/percentage")
        if headwind_mps < 0:
            raise ValueError("headwind_mps must be non-negative")
        wind_ratio = min(1.5, headwind_mps / self.policy.maximum_headwind_mps)
        duration_h = candidate.estimated_duration_s / 3600.0
        cruise = duration_h * (self.policy.cruise_power_w * (1.0 + 0.75 * wind_ratio) + self.policy.avionics_power_w)
        positive_climb_m = sum(
            max(0.0, current.altitude_m - previous.altitude_m)
            for previous, current in zip(candidate.points, candidate.points[1:])
        )
        estimated = cruise + positive_climb_m * self.policy.climb_energy_wh_per_m
        available = battery_capacity_wh * battery_percent / 100.0
        reserve = battery_capacity_wh * self.policy.reserve_ratio
        margin = available - reserve - estimated
        gates = [
            GateResult(
                "ENERGY_RESERVE", GateStatus.PASS if margin >= 0 else GateStatus.FAIL,
                "route preserves configured reserve" if margin >= 0 else "route would consume configured reserve",
                {"estimated_wh": estimated, "available_wh": available, "margin_wh": margin},
                {"reserve_wh": reserve, "reserve_ratio": self.policy.reserve_ratio},
            ),
            GateResult(
                "WIND_ENVELOPE", GateStatus.PASS if headwind_mps <= self.policy.maximum_headwind_mps else GateStatus.WARN,
                "headwind is within analysis envelope" if headwind_mps <= self.policy.maximum_headwind_mps else "headwind exceeds calibrated envelope; estimate is capped",
                {"headwind_mps": headwind_mps}, {"maximum_mps": self.policy.maximum_headwind_mps},
            ),
        ]
        return EnergyAssessment(margin >= 0, estimated, available, reserve, margin, wind_ratio, tuple(gates))
