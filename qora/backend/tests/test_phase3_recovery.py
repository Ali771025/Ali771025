"""Reliability recovery must use explicit permissions and never route around policy."""
from app.core.db import SessionLocal
from app.modules.service.service import ServiceRegistry


def test_model_failure_uses_direct_qora_then_authorized_fallback_service(client, emma):
    services = client.get("/api/v1/services?intent=job_interview_preparation", headers=emma).json()
    original = next(item["service"] for item in services if item["service"]["name"] == "Interview Coach")
    admin_token = client.post("/api/v1/auth/login", json={
        "email": "admin@qora.ai", "password": "admin123",
    }).json()["access_token"]
    admin = {"Authorization": "Bearer " + admin_token}
    old_weights = client.get("/api/v1/services/admin/ranking-weights", headers=admin).json()["weights"]
    client.put("/api/v1/services/admin/ranking-weights", json={
        key: (0.5 if key in ("intent_relevance", "personal_fit") else 0.0)
        for key in old_weights
    }, headers=admin)

    with SessionLocal() as db:
        primary = ServiceRegistry.get(db, original["id"])
        primary_version = ServiceRegistry.current_version(db, primary)
        old_instructions = primary_version.system_instructions
        primary_version.system_instructions = "SIMULATE_FAILURE"
        creator_id = primary.creator_id
        db.commit()

        backup = ServiceRegistry.create(db, creator_id, {
            "name": "Interview Coach Backup",
            "summary": "Extra practice and structured interview feedback",
            "description": "A second safe option for job interview preparation.",
            "purpose": "Guide people through realistic interview practice",
            "audience": "job seekers preparing for interviews",
            "category": "career",
            "risk_level": "MEDIUM",
            "intent_slugs": ["job_interview_preparation"],
            "capability_slugs": ["interview_coaching"],
        })
        backup_version = ServiceRegistry.add_version(db, backup, {
            "purpose": "Interview practice with structured feedback",
            "method": "guided questions and a short practice plan",
            "behavior": "supportive, practical, and concise",
            "system_instructions": "You are an interview practice coach. Provide a concrete practice plan.",
            "boundaries": "No guarantees or legal, medical, or financial advice.",
            "outcome_definition": {"text": "A practical interview practice plan", "signals": ["deliverable_generated"]},
            "knowledge_config": {},
            "tools_config": {},
            "model_requirements": {},
            "context_requirements": [],
            "examples": [],
        })
        for status in ("ready_for_test", "testing", "qualification_pending", "ready", "published"):
            ServiceRegistry._transition(db, backup, status, "recovery integration test", actor_id=3)
        backup_id = backup.id
        db.commit()

    try:
        # The original service is allowed; the backup is not. Context is never shared across services.
        grant = client.post("/api/v1/permissions/grants", json={
            "service_id": original["id"], "context_type": "career", "mode": "ALWAYS_ALLOW",
        }, headers=emma)
        assert grant.status_code == 201
        conversation = client.post("/api/v1/conversations", headers=emma).json()
        direct = client.post(f"/api/v1/conversations/{conversation['id']}/messages", json={
            "content": "Help me prepare for a Product Manager interview next week",
        }, headers=emma).json()
        assert direct["message"]["content_blocks"]["recovery"]["recovery_action"] == "direct_qora"
        assert direct["outcome"] is None

        client.post("/api/v1/permissions/grants", json={
            "service_id": backup_id, "context_type": "career", "mode": "ALWAYS_ALLOW",
        }, headers=emma)
        conversation2 = client.post("/api/v1/conversations", headers=emma).json()
        recovered = client.post(f"/api/v1/conversations/{conversation2['id']}/messages", json={
            "content": "Help me prepare for a Product Manager interview next week",
        }, headers=emma).json()
        assert recovered["service_response"]["ok"] is True, {
            "recovery": recovered.get("recovery"),
            "service_match": recovered.get("service_match"),
            "content": recovered.get("message", {}).get("content"),
            "blocks": recovered.get("message", {}).get("content_blocks"),
        }
        assert recovered["service_match"]["chosen_service_id"] == backup_id
        assert recovered["outcome"] is not None
    finally:
        with SessionLocal() as db:
            current = ServiceRegistry.current_version(db, ServiceRegistry.get(db, original["id"]))
            current.system_instructions = old_instructions
            db.commit()
        client.put("/api/v1/services/admin/ranking-weights", json=old_weights, headers=admin)
