from __future__ import annotations

import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

try:
    from fastapi.testclient import TestClient
    API_AVAILABLE = True
except ImportError:
    TestClient = None  # type: ignore[assignment]
    API_AVAILABLE = False

from safe_autonomy.health_manager import HealthPolicy
from safe_autonomy.mission_api import create_app
from test_dynamic_energy_v06 import route_fixture


@unittest.skipUnless(API_AVAILABLE, "mission-api optional dependencies are not installed")
class MissionApiV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.client_context = TestClient(create_app(str(Path(self.temporary.name) / "api.sqlite3"), "config/flight_scenarios.json"))
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.temporary.cleanup()

    def test_health_and_temporal_gate(self) -> None:
        self.assertEqual(self.client.get("/health").json()["version"], "0.6.0-dev1")
        response = self.client.post("/api/v2/time/observe", json={
            "source": "gps", "sequence": 1,
            "source_monotonic_ms": 995, "received_monotonic_ms": 1000,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["verdict"], "ACCEPT")

    def test_control_fields_are_rejected_by_analysis_adapter(self) -> None:
        candidate = asdict(route_fixture())
        candidate["vehicle_command"] = {"command": "ARM"}
        response = self.client.post("/api/v2/routes/energy", json={
            "candidate": candidate, "battery_capacity_wh": 1000, "battery_percent": 90,
        })
        self.assertEqual(response.status_code, 422)

    def test_map_plan_readiness_and_assurance_flow(self) -> None:
        content = Path("maps/sample_mission.geojson").read_bytes()
        upload = self.client.post("/api/v1/maps/upload", files={"file": ("sample.geojson", content, "application/geo+json")})
        self.assertEqual(upload.status_code, 200)
        map_id = upload.json()["map_id"]
        plan = self.client.post("/api/v1/routes/plan", json={
            "map_id": map_id, "start_x_m": 10, "start_y_m": 10,
            "goal_x_m": 180, "goal_y_m": 125, "start_altitude_m": 25,
            "cruise_altitude_m": 60, "policy": {"requested_alternatives": 3},
        })
        self.assertEqual(plan.status_code, 200)
        candidate = plan.json()["candidates"][0]
        for module in HealthPolicy().required_modules + HealthPolicy().optional_modules:
            response = self.client.post("/api/v2/health/heartbeat", json={
                "module_id": module, "observed_monotonic_ms": 1000,
                "status": "HEALTHY", "latency_ms": 5,
            })
            self.assertEqual(response.status_code, 200)
        assurance = self.client.post("/api/v2/assurance/evaluate", json={
            "mission_id": "api-test", "map_id": map_id, "candidate": candidate,
            "now_monotonic_ms": 1050, "battery_capacity_wh": 2000,
            "battery_percent": 90, "headwind_mps": 2, "created_at_ms": 2000,
        })
        self.assertEqual(assurance.status_code, 200)
        self.assertEqual(assurance.json()["overall_status"], "PASS")
