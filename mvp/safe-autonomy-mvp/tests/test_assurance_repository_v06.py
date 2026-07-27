from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from safe_autonomy.assurance_contracts import GateStatus, ModuleHeartbeat
from safe_autonomy.assurance_repository import AssuranceRepository
from safe_autonomy.database import Database
from safe_autonomy.energy_model import RouteEnergyEstimator
from safe_autonomy.health_manager import HealthPolicy, SystemHealthManager
from safe_autonomy.map_ingestion import MapAnalyzer
from safe_autonomy.mission_assurance import MissionAssuranceEngine
from safe_autonomy.observability import LatencyRegistry
from safe_autonomy.temporal_guard import TemporalGuard
from test_dynamic_energy_v06 import map_fixture, route_fixture


class AssuranceRepositoryTests(unittest.TestCase):
    def test_migration_six_and_full_report_are_transactionally_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "v06.sqlite3")
            database.migrate()
            versions = [row[0] for row in database.connection.execute("SELECT version FROM schema_migrations ORDER BY version")]
            self.assertEqual(versions[-1], 7)
            repository = AssuranceRepository(database)
            temporal = TemporalGuard().observe("gps", 1, 995, 1000)
            repository.save_temporal(temporal)
            policy = HealthPolicy(required_modules=("planner",), optional_modules=())
            health = SystemHealthManager(policy)
            health.record(ModuleHeartbeat("planner", 1000, "HEALTHY", 5))
            readiness = health.evaluate(1010)
            energy = RouteEnergyEstimator().evaluate(route_fixture(), 1000, 90)
            report = MissionAssuranceEngine().evaluate("mission-1", MapAnalyzer().analyze(map_fixture()), route_fixture(), readiness, energy, 2000)
            repository.save_report(report)
            metrics = LatencyRegistry(10)
            metrics.observe("planner", 12)
            repository.save_slo(metrics.snapshot("planner", 100), 2000)
            self.assertEqual(database.connection.execute("SELECT COUNT(*) FROM temporal_observations").fetchone()[0], 1)
            self.assertEqual(database.connection.execute("SELECT COUNT(*) FROM assurance_reports").fetchone()[0], 1)
            self.assertEqual(database.connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            database.close()

    def test_assurance_hash_is_reproducible_and_failure_propagates(self) -> None:
        policy = HealthPolicy(required_modules=("planner",), optional_modules=())
        health = SystemHealthManager(policy)
        readiness = health.evaluate(1000)
        energy = RouteEnergyEstimator().evaluate(route_fixture(3600), 100, 10)
        engine = MissionAssuranceEngine()
        first = engine.evaluate("m", MapAnalyzer().analyze(map_fixture()), route_fixture(), readiness, energy, 1)
        second = engine.evaluate("m", MapAnalyzer().analyze(map_fixture()), route_fixture(), readiness, energy, 2)
        self.assertEqual(first.overall_status, GateStatus.FAIL)
        self.assertEqual(first.input_sha256, second.input_sha256)
