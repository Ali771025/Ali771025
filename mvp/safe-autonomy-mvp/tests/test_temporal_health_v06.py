from __future__ import annotations

import unittest

from safe_autonomy.assurance_contracts import ModuleHeartbeat, ReadinessState, TemporalVerdict
from safe_autonomy.health_manager import HealthPolicy, SystemHealthManager
from safe_autonomy.temporal_guard import TemporalGuard, TemporalPolicy


class TemporalGuardTests(unittest.TestCase):
    def test_accepts_fresh_monotonic_sequence(self) -> None:
        guard = TemporalGuard()
        result = guard.observe("imu", 1, 995, 1000)
        self.assertEqual(result.verdict, TemporalVerdict.ACCEPT)

    def test_rejects_out_of_order_without_poisoning_state(self) -> None:
        guard = TemporalGuard()
        guard.observe("imu", 10, 1000, 1005)
        rejected = guard.observe("imu", 9, 1001, 1006)
        accepted = guard.observe("imu", 11, 1002, 1007)
        self.assertEqual(rejected.verdict, TemporalVerdict.REJECT)
        self.assertIn("OUT_OF_ORDER_SEQUENCE", rejected.reasons)
        self.assertEqual(accepted.verdict, TemporalVerdict.ACCEPT)

    def test_stale_future_and_cross_source_skew_are_explicit(self) -> None:
        guard = TemporalGuard(TemporalPolicy(maximum_age_ms=100, maximum_future_ms=10, maximum_cross_source_skew_ms=20))
        guard.observe("gps", 1, 1000, 1005)
        skewed = guard.observe("camera", 1, 1050, 1055)
        stale = guard.observe("baro", 1, 800, 1000)
        future = guard.observe("mag", 1, 1100, 1000)
        self.assertEqual(skewed.verdict, TemporalVerdict.DEGRADED)
        self.assertIn("CROSS_SOURCE_SKEW", skewed.reasons)
        self.assertEqual(stale.verdict, TemporalVerdict.REJECT)
        self.assertEqual(future.verdict, TemporalVerdict.REJECT)

    def test_old_peer_does_not_create_permanent_cross_source_skew(self) -> None:
        guard = TemporalGuard(TemporalPolicy(maximum_age_ms=100, maximum_cross_source_skew_ms=20))
        guard.observe("gps", 1, 1000, 1000)
        result = guard.observe("camera", 1, 5000, 5000)
        self.assertEqual(result.verdict, TemporalVerdict.ACCEPT)


class HealthManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = HealthPolicy(required_modules=("telemetry", "planner"), optional_modules=("rag",), maximum_heartbeat_age_ms=100)
        self.manager = SystemHealthManager(self.policy)

    def test_missing_required_module_is_not_ready(self) -> None:
        self.manager.record(ModuleHeartbeat("telemetry", 1000, "HEALTHY", 5.0))
        self.assertEqual(self.manager.evaluate(1010).state, ReadinessState.NOT_READY)

    def test_optional_failure_degrades_but_does_not_block(self) -> None:
        self.manager.record(ModuleHeartbeat("telemetry", 1000, "HEALTHY", 5.0))
        self.manager.record(ModuleHeartbeat("planner", 1000, "HEALTHY", 10.0))
        self.manager.record(ModuleHeartbeat("rag", 1000, "FAILED", 10.0))
        self.assertEqual(self.manager.evaluate(1010).state, ReadinessState.DEGRADED)

    def test_all_fresh_modules_are_ready(self) -> None:
        for module in ("telemetry", "planner", "rag"):
            self.manager.record(ModuleHeartbeat(module, 1000, "HEALTHY", 5.0))
        self.assertEqual(self.manager.evaluate(1010).state, ReadinessState.READY)

    def test_clock_regression_is_rejected(self) -> None:
        self.manager.record(ModuleHeartbeat("telemetry", 1000, "HEALTHY", 5.0))
        with self.assertRaises(ValueError):
            self.manager.record(ModuleHeartbeat("telemetry", 999, "HEALTHY", 5.0))
