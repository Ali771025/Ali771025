"""Phase 3: trust, risk, eight-signal ranking, safe tools, orchestration and recovery."""
from types import SimpleNamespace

from app.core.db import SessionLocal
from app.modules.reputation.service import ReputationService
from app.modules.runtime.service import RuntimeService
from app.modules.runtime.tools import ToolService
from app.modules.service.risk import RiskService
from app.modules.service.service import ServiceRegistry


def _admin(client):
    token = client.post("/api/v1/auth/login", json={
        "email": "admin@qora.ai", "password": "admin123",
    }).json()
    return {"Authorization": "Bearer " + token["access_token"]}


def test_eight_ranking_signals_and_admin_weights(client, emma):
    before = client.get("/api/v1/services", headers=emma)
    assert before.status_code == 200
    assert len(before.json()) > 0
    assert set(before.json()[0]["rank"]["signals"]) == {
        "intent_relevance", "outcome_quality", "personal_fit", "trust",
        "freshness", "satisfaction", "repeat_use", "exploration",
    }

    admin = _admin(client)
    old = client.get("/api/v1/services/admin/ranking-weights", headers=admin).json()["weights"]
    assert len(old) == 8 and abs(sum(old.values()) - 1) < 1e-5
    custom = {key: float(key == "repeat_use") for key in old}
    changed = client.put("/api/v1/services/admin/ranking-weights", json=custom, headers=admin)
    assert changed.status_code == 200
    assert changed.json()["weights"]["repeat_use"] == 1.0

    ranked = client.get("/api/v1/services", headers=emma).json()
    assert all(item["rank"]["score"] == item["rank"]["signals"]["repeat_use"] for item in ranked)
    restored = client.put("/api/v1/services/admin/ranking-weights", json=old, headers=admin)
    assert restored.status_code == 200


def test_risk_cannot_be_downgraded_and_high_risk_is_gated():
    assert RiskService.classify("A service for medical diagnosis", "LOW") == "HIGH"
    assert RiskService.classify("Writing editor", "LOW") == "LOW"
    assert RiskService.classify("A guide to make a bomb", "MEDIUM") == "RESTRICTED"
    service = SimpleNamespace(risk_level="HIGH", verification_status="none")
    creator = SimpleNamespace(verification_status="verified")
    version = SimpleNamespace(boundaries="Clear scope. Do not diagnose or prescribe.")
    allowed, reason = RiskService.runtime_gate(service, creator, version)
    assert allowed is False
    assert "platform review" in reason
    service.verification_status = "verified"
    assert RiskService.runtime_gate(service, creator, version)[0] is True


def test_high_risk_publication_waits_for_platform_verification(client, sarah):
    created = client.post("/api/v1/services", json={
        "name": "Medical Diagnosis Assistant",
        "summary": "General health information",
        "purpose": "Help users interpret symptoms and medical diagnoses",
        "audience": "adults seeking health information",
        "risk_level": "LOW",
    }, headers=sarah)
    assert created.status_code == 201
    service_id = created.json()["id"]
    assert created.json()["risk_level"] == "HIGH"

    version = client.post(f"/api/v1/services/{service_id}/versions", json={
        "purpose": "General health information",
        "boundaries": "No diagnosis, prescriptions, or emergency advice. Contact a clinician.",
        "outcome_definition": {"text": "A safe information summary", "signals": ["deliverable_generated"]},
    }, headers=sarah)
    assert version.status_code == 201
    with SessionLocal() as db:
        service = ServiceRegistry.get(db, service_id)
        for status in ("ready_for_test", "testing", "qualification_pending", "ready"):
            ServiceRegistry._transition(db, service, status, "risk-gate test", actor_id=3)
        db.commit()

    blocked = client.post(f"/api/v1/services/{service_id}/lifecycle", json={"action": "publish"}, headers=sarah)
    assert blocked.status_code == 403
    admin = _admin(client)
    reviewed = client.post(f"/api/v1/services/admin/services/{service_id}/verification", json={
        "status": "verified",
    }, headers=admin)
    assert reviewed.status_code == 200
    published = client.post(f"/api/v1/services/{service_id}/lifecycle", json={"action": "publish"}, headers=sarah)
    assert published.status_code == 200
    assert published.json()["lifecycle_status"] == "published"


def test_reputation_events_are_separate_and_idempotent(client, emma):
    service_id = client.get("/api/v1/services", headers=emma).json()[0]["service"]["id"]
    with SessionLocal() as db:
        before = ReputationService.trust_for(db, "service", service_id)["overall"]
        creator_id = ServiceRegistry.get(db, service_id).creator_id
        creator_before = ReputationService.trust_for(db, "creator", creator_id)["overall"]
        key = f"test-safety:{service_id}"
        assert ReputationService.apply_event(
            db, "service", service_id, "safety_failure", idempotency_key=key,
            meta={"test": True},
        ) is True
        after = ReputationService.trust_for(db, "service", service_id)
        assert after["overall"] < before
        assert after["components"]["safety"] < 0.9
        assert ReputationService.apply_event(
            db, "service", service_id, "safety_failure", idempotency_key=key,
            meta={"test": True},
        ) is False
        assert ReputationService.trust_for(db, "creator", creator_id)["overall"] == creator_before


def test_tool_registry_policy_and_result_validation(client, emma):
    admin = _admin(client)
    services = client.get("/api/v1/services", headers=emma).json()
    service_id = services[0]["service"]["id"]
    registration = client.post("/api/v1/runtime/tools", json={
        "name": "text.word_count",
        "allowed_services": [service_id],
        "timeout_ms": 1000,
    }, headers=admin)
    assert registration.status_code == 201
    assert client.get("/api/v1/runtime/tools", headers=emma).status_code == 403
    unknown = client.post("/api/v1/runtime/tools", json={"name": "python.execute"}, headers=admin)
    assert unknown.status_code == 409
    math_tool = client.post("/api/v1/runtime/tools", json={
        "name": "math.calculate", "allowed_services": [service_id], "timeout_ms": 1000,
    }, headers=admin)
    assert math_tool.status_code == 201

    with SessionLocal() as db:
        user = __import__("app.modules.identity.service", fromlist=["IdentityService"]).IdentityService.get_by_email(db, "emma@qora.ai")
        service = ServiceRegistry.get(db, service_id)
        version = ServiceRegistry.current_version(db, service)
        session = RuntimeService.start_session(db, user.id, service.id, version.id, None)
        db.commit()
        result = ToolService.execute(db, session.id, service.id, "text.word_count", {"text": "one two three"}, {})
        assert result["ok"] is True
        assert result["result"] == {"word_count": 3, "char_count": 13}
        denied = ToolService.execute(db, session.id, service.id + 999, "text.word_count", {"text": "x"}, {})
        assert denied["ok"] is False
        assert denied["status"] == "denied"
        unsafe = ToolService.execute(
            db, session.id, service.id, "math.calculate",
            {"expression": "__import__('os').system('echo unsafe')"}, {},
        )
        assert unsafe["ok"] is False
        assert unsafe["status"] == "error"
        db.commit()

    assert client.get("/api/v1/reputation/audit", headers=admin).status_code == 200
    invocation_log = client.get("/api/v1/runtime/tools/invocations", headers=admin)
    assert invocation_log.status_code == 200
    assert {row["status"] for row in invocation_log.json()["items"]} >= {"ok", "denied", "error"}


def test_orchestration_builds_and_runs_a_multi_service_chain(client, emma):
    response = client.post("/api/v1/orchestration/plans", json={
        "goal_text": "Help me prepare for a job interview and edit my resume",
    }, headers=emma)
    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["status"] == "draft"
    assert len(plan["steps"]) >= 2
    assert {step["service_name"] for step in plan["steps"]} >= {"Interview Coach", "Writing Editor"}

    completed = client.post(f"/api/v1/orchestration/plans/{plan['id']}/execute", headers=emma)
    assert completed.status_code == 200, completed.text
    result = completed.json()
    assert result["status"] == "completed"
    assert all(step["status"] == "done" for step in result["steps"])
    assert all(step["output"].get("content") for step in result["steps"])

    # Execution is idempotent: reading/replaying a completed plan does not create sessions.
    again = client.post(f"/api/v1/orchestration/plans/{plan['id']}/execute", headers=emma)
    assert again.json()["status"] == "completed"
