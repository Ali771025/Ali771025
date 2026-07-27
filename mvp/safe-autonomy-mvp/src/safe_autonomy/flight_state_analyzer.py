from __future__ import annotations

from dataclasses import dataclass

from .mission_contracts import (
    FindingSeverity,
    FlightAssessment,
    FlightFinding,
    FlightPhase,
    FlightSample,
    SafeRecommendation,
)


@dataclass(frozen=True, slots=True)
class FlightAnalysisPolicy:
    battery_return_percent: float = 30.0
    battery_land_percent: float = 15.0
    minimum_gps_quality: float = 0.60
    minimum_link_quality: float = 0.25
    maximum_telemetry_age_ms: int = 500
    maximum_route_deviation_m: float = 15.0
    warning_route_deviation_m: float = 5.0
    critical_obstacle_ttc_s: float = 5.0
    minimum_terrain_clearance_m: float = 20.0
    maximum_tilt_deg: float = 55.0
    maximum_ground_speed_mps: float = 30.0
    maximum_climb_rate_mps: float = 6.0
    maximum_descent_rate_mps: float = 4.0
    maximum_map_age_ms: int = 86_400_000


_SEVERITY_RANK = {
    FindingSeverity.INFO: 0,
    FindingSeverity.WARNING: 1,
    FindingSeverity.HIGH: 2,
    FindingSeverity.CRITICAL: 3,
}

_ACTION_RANK = {
    SafeRecommendation.CONTINUE: 0,
    SafeRecommendation.REQUEST_SENSOR_UPDATE: 1,
    SafeRecommendation.REQUEST_REPLAN: 2,
    SafeRecommendation.HOLD: 3,
    SafeRecommendation.RETURN: 4,
    SafeRecommendation.LAND: 5,
    SafeRecommendation.ABORT: 6,
}


class FlightStateAnalyzer:
    _ALLOWED_TRANSITIONS: dict[FlightPhase, set[FlightPhase]] = {
        FlightPhase.PREFLIGHT: {FlightPhase.PREFLIGHT, FlightPhase.TAKEOFF, FlightPhase.EMERGENCY},
        FlightPhase.TAKEOFF: {FlightPhase.TAKEOFF, FlightPhase.CLIMB, FlightPhase.HOLD, FlightPhase.LANDING, FlightPhase.EMERGENCY},
        FlightPhase.CLIMB: {FlightPhase.CLIMB, FlightPhase.CRUISE, FlightPhase.HOLD, FlightPhase.RETURN, FlightPhase.EMERGENCY},
        FlightPhase.CRUISE: {FlightPhase.CRUISE, FlightPhase.HOLD, FlightPhase.RETURN, FlightPhase.APPROACH, FlightPhase.EMERGENCY},
        FlightPhase.HOLD: {FlightPhase.HOLD, FlightPhase.CRUISE, FlightPhase.RETURN, FlightPhase.LANDING, FlightPhase.EMERGENCY},
        FlightPhase.RETURN: {FlightPhase.RETURN, FlightPhase.HOLD, FlightPhase.APPROACH, FlightPhase.EMERGENCY},
        FlightPhase.APPROACH: {FlightPhase.APPROACH, FlightPhase.LANDING, FlightPhase.HOLD, FlightPhase.RETURN, FlightPhase.EMERGENCY},
        FlightPhase.LANDING: {FlightPhase.LANDING, FlightPhase.LANDED, FlightPhase.HOLD, FlightPhase.EMERGENCY},
        FlightPhase.LANDED: {FlightPhase.LANDED, FlightPhase.PREFLIGHT, FlightPhase.TAKEOFF},
        FlightPhase.EMERGENCY: {FlightPhase.EMERGENCY, FlightPhase.HOLD, FlightPhase.LANDING, FlightPhase.LANDED},
    }

    def __init__(self, policy: FlightAnalysisPolicy | None = None) -> None:
        self.policy = policy or FlightAnalysisPolicy()

    def analyze(
        self,
        sample: FlightSample,
        created_at_ms: int,
        previous_phase: FlightPhase | None = None,
    ) -> FlightAssessment:
        phase = self.infer_phase(sample)
        findings: list[tuple[FlightFinding, SafeRecommendation]] = []

        def add(code: str, severity: FindingSeverity, message: str, observed: dict, limit: dict, action: SafeRecommendation) -> None:
            findings.append((FlightFinding(code, severity, message, observed, limit), action))

        transition_valid = previous_phase is None or phase in self._ALLOWED_TRANSITIONS[previous_phase]
        if not transition_valid:
            add(
                "ILLEGAL_PHASE_TRANSITION", FindingSeverity.HIGH,
                f"Unexpected flight-phase transition {previous_phase.value} -> {phase.value}",
                {"previous": previous_phase.value, "current": phase.value},
                {"allowed": sorted(item.value for item in self._ALLOWED_TRANSITIONS[previous_phase])},
                SafeRecommendation.HOLD,
            )
        if not sample.estimator_healthy:
            add("ESTIMATOR_UNHEALTHY", FindingSeverity.CRITICAL, "PX4 estimator health is false", {"healthy": False}, {"required": True}, SafeRecommendation.HOLD)
        if sample.telemetry_age_ms > self.policy.maximum_telemetry_age_ms:
            add("TELEMETRY_STALE", FindingSeverity.CRITICAL, "Telemetry is older than the freshness limit", {"age_ms": sample.telemetry_age_ms}, {"max_ms": self.policy.maximum_telemetry_age_ms}, SafeRecommendation.HOLD)
        if sample.gps_quality < self.policy.minimum_gps_quality:
            severity = FindingSeverity.CRITICAL if sample.gps_quality < 0.30 else FindingSeverity.HIGH
            add("GPS_DEGRADED", severity, "GPS quality is below the navigation threshold", {"quality": sample.gps_quality}, {"min": self.policy.minimum_gps_quality}, SafeRecommendation.HOLD)
        if sample.battery_percent <= self.policy.battery_land_percent:
            add("BATTERY_CRITICAL", FindingSeverity.CRITICAL, "Battery reached the landing reserve", {"percent": sample.battery_percent}, {"land_at_or_below": self.policy.battery_land_percent}, SafeRecommendation.LAND)
        elif sample.battery_percent <= self.policy.battery_return_percent:
            add("BATTERY_RETURN", FindingSeverity.HIGH, "Battery reached the return reserve", {"percent": sample.battery_percent}, {"return_at_or_below": self.policy.battery_return_percent}, SafeRecommendation.RETURN)
        if sample.link_quality < self.policy.minimum_link_quality:
            add("LINK_LOSS", FindingSeverity.CRITICAL, "Command/telemetry link quality is below threshold", {"quality": sample.link_quality}, {"min": self.policy.minimum_link_quality}, SafeRecommendation.RETURN)
        if sample.geofence_margin_m < 0:
            add("GEOFENCE_BREACH", FindingSeverity.CRITICAL, "Position is outside the configured geofence", {"margin_m": sample.geofence_margin_m}, {"minimum_m": 0.0}, SafeRecommendation.RETURN)
        elif sample.geofence_margin_m < 10:
            add("GEOFENCE_NEAR", FindingSeverity.WARNING, "Position is close to the geofence boundary", {"margin_m": sample.geofence_margin_m}, {"warning_below_m": 10.0}, SafeRecommendation.REQUEST_REPLAN)
        if sample.route_deviation_m > self.policy.maximum_route_deviation_m:
            add("ROUTE_DEVIATION_HIGH", FindingSeverity.HIGH, "Vehicle deviated materially from the validated route", {"deviation_m": sample.route_deviation_m}, {"max_m": self.policy.maximum_route_deviation_m}, SafeRecommendation.REQUEST_REPLAN)
        elif sample.route_deviation_m > self.policy.warning_route_deviation_m:
            add("ROUTE_DEVIATION_WARNING", FindingSeverity.WARNING, "Route deviation is increasing", {"deviation_m": sample.route_deviation_m}, {"warning_m": self.policy.warning_route_deviation_m}, SafeRecommendation.REQUEST_REPLAN)
        if sample.obstacle_ttc_s is not None and sample.obstacle_ttc_s <= self.policy.critical_obstacle_ttc_s:
            add("OBSTACLE_TTC", FindingSeverity.CRITICAL, "Calibrated tracking reports a TTC violation", {"ttc_s": sample.obstacle_ttc_s}, {"minimum_s": self.policy.critical_obstacle_ttc_s}, SafeRecommendation.HOLD)
        if sample.terrain_clearance_m is not None and sample.terrain_clearance_m < self.policy.minimum_terrain_clearance_m:
            add("TERRAIN_CLEARANCE", FindingSeverity.CRITICAL, "Terrain clearance is below the configured minimum", {"clearance_m": sample.terrain_clearance_m}, {"minimum_m": self.policy.minimum_terrain_clearance_m}, SafeRecommendation.HOLD)
        if max(abs(sample.roll_deg), abs(sample.pitch_deg)) > self.policy.maximum_tilt_deg:
            add("EXCESSIVE_TILT", FindingSeverity.CRITICAL, "Attitude tilt exceeds the analysis envelope", {"roll_deg": sample.roll_deg, "pitch_deg": sample.pitch_deg}, {"maximum_abs_deg": self.policy.maximum_tilt_deg}, SafeRecommendation.ABORT)
        if sample.ground_speed_mps > self.policy.maximum_ground_speed_mps:
            add("EXCESSIVE_GROUND_SPEED", FindingSeverity.HIGH, "Ground speed exceeds the analysis envelope", {"speed_mps": sample.ground_speed_mps}, {"maximum_mps": self.policy.maximum_ground_speed_mps}, SafeRecommendation.HOLD)
        if sample.vertical_speed_mps > self.policy.maximum_climb_rate_mps:
            add("EXCESSIVE_CLIMB", FindingSeverity.HIGH, "Climb rate exceeds the analysis envelope", {"vertical_speed_mps": sample.vertical_speed_mps}, {"maximum_mps": self.policy.maximum_climb_rate_mps}, SafeRecommendation.HOLD)
        if sample.vertical_speed_mps < -self.policy.maximum_descent_rate_mps:
            add("EXCESSIVE_DESCENT", FindingSeverity.CRITICAL, "Descent rate exceeds the analysis envelope", {"vertical_speed_mps": sample.vertical_speed_mps}, {"minimum_mps": -self.policy.maximum_descent_rate_mps}, SafeRecommendation.HOLD)
        if phase == FlightPhase.TAKEOFF and sample.phase_elapsed_s > 10 and sample.altitude_agl_m < 1.0:
            add("TAKEOFF_NO_CLIMB", FindingSeverity.CRITICAL, "Takeoff phase has not produced expected altitude gain", {"elapsed_s": sample.phase_elapsed_s, "altitude_agl_m": sample.altitude_agl_m}, {"max_elapsed_s": 10, "minimum_altitude_m": 1.0}, SafeRecommendation.ABORT)
        if phase in {FlightPhase.APPROACH, FlightPhase.LANDING} and not sample.landing_zone_clear:
            add("LANDING_ZONE_BLOCKED", FindingSeverity.CRITICAL, "Landing zone is not confirmed clear", {"clear": False}, {"required": True}, SafeRecommendation.HOLD)
        if not sample.camera_healthy:
            add("CAMERA_UNAVAILABLE", FindingSeverity.WARNING, "Camera stream is unavailable", {"healthy": False}, {"required_for_perception": True}, SafeRecommendation.REQUEST_SENSOR_UPDATE)
        if not sample.tracker_healthy:
            add("TRACKER_UNAVAILABLE", FindingSeverity.WARNING, "Object tracker is unavailable", {"healthy": False}, {"required_for_ttc": True}, SafeRecommendation.REQUEST_SENSOR_UPDATE)
        if sample.map_age_ms > self.policy.maximum_map_age_ms:
            add("MAP_STALE", FindingSeverity.WARNING, "Uploaded map is older than the configured analysis limit", {"age_ms": sample.map_age_ms}, {"max_ms": self.policy.maximum_map_age_ms}, SafeRecommendation.REQUEST_SENSOR_UPDATE)

        if findings:
            highest = max((finding.severity for finding, _ in findings), key=lambda item: _SEVERITY_RANK[item])
            recommendation = max((action for _, action in findings), key=lambda item: _ACTION_RANK[item])
        else:
            highest = FindingSeverity.INFO
            recommendation = SafeRecommendation.CONTINUE
        penalty = sum({FindingSeverity.INFO: 0, FindingSeverity.WARNING: 7, FindingSeverity.HIGH: 18, FindingSeverity.CRITICAL: 35}[finding.severity] for finding, _ in findings)
        score = max(0.0, min(100.0, 100.0 - penalty))
        return FlightAssessment(
            sample, phase, previous_phase, transition_valid, score, highest,
            recommendation, tuple(finding for finding, _ in findings), created_at_ms,
        )

    @staticmethod
    def infer_phase(sample: FlightSample) -> FlightPhase:
        mode = sample.reported_mode.upper()
        if mode in {"EMERGENCY", "TERMINATION"}:
            return FlightPhase.EMERGENCY
        if mode in {"RTL", "RETURN", "RTH"}:
            return FlightPhase.RETURN
        if mode in {"HOLD", "LOITER"}:
            return FlightPhase.HOLD
        if not sample.armed:
            return FlightPhase.LANDED if sample.landed else FlightPhase.PREFLIGHT
        if sample.landed or (sample.altitude_agl_m < 1.0 and sample.vertical_speed_mps > 0.2):
            return FlightPhase.TAKEOFF
        if mode in {"LAND", "LANDING"} or (sample.altitude_agl_m < 5.0 and sample.vertical_speed_mps < -0.2):
            return FlightPhase.LANDING
        if sample.distance_to_goal_m < 30.0 and sample.vertical_speed_mps < -0.2:
            return FlightPhase.APPROACH
        if sample.vertical_speed_mps > 0.5:
            return FlightPhase.CLIMB
        return FlightPhase.CRUISE
