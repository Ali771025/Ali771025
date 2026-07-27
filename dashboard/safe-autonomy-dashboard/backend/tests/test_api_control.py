import time

from fastapi.testclient import TestClient

from flight_dashboard.main import create_app
from flight_dashboard.settings import Settings


def authorization(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"authorization": f"Bearer {response.json()['access_token']}"}


def test_login_bootstrap_and_dual_approval(tmp_path):
    settings = Settings(
        env="test",
        database_path=tmp_path / "dashboard.db",
        jwt_secret="test-secret-that-is-long-enough-123456",
        expert_username="pilot-expert",
        expert_password="expert-pass",
        manager_username="flight-manager",
        manager_password="manager-pass",
        udp_port=0,
        tcp_port=0,
        control_mode="simulation",
        control_require_dual_approval=True,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        now = int(time.time() * 1000)
        app.state.runtime.hub.latest["telemetry"] = {
            "topic": "telemetry", "received_at_ms": now, "sent_at_ms": now, "latency_ms": 0,
            "payload": {"gps_fix": 3, "battery_percent": 85, "ekf_healthy": True},
        }
        expert = authorization(client, "pilot-expert", "expert-pass")
        manager = authorization(client, "flight-manager", "manager-pass")
        bootstrap = client.get("/api/v1/dashboard/bootstrap", headers=expert)
        assert bootstrap.status_code == 200
        assert bootstrap.json()["capabilities"]["model_control_authority"] is False

        ticket = client.post("/api/v1/ws-ticket", headers=expert).json()["ticket"]
        with client.websocket_connect(f"/ws/live?ticket={ticket}") as websocket:
            snapshot = websocket.receive_json()
            assert snapshot["type"] == "snapshot"
            assert snapshot["username"] == "pilot-expert"

        requested = client.post(
            "/api/v1/control/intents",
            headers=expert,
            json={"action": "ARM", "reason": "preflight checklist complete", "idempotency_key": "intent-key-0001"},
        )
        assert requested.status_code == 200
        assert requested.json()["status"] == "PENDING_APPROVAL"

        approved = client.post(
            f"/api/v1/control/intents/{requested.json()['id']}/approve",
            headers=manager,
            json={"note": "manager cross-check complete"},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "EXECUTED"
        assert 'simulation' in approved.json()["result_json"]
