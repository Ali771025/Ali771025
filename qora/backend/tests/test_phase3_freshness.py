"""Freshness is reflected in Explore, trust components and restoration after verification."""
from datetime import datetime, timedelta, timezone

from app.core.db import SessionLocal
from app.modules.knowledge.models import KnowledgeSource
from app.modules.service.service import ServiceRegistry


def test_stale_training_material_lowers_rank_and_trust_then_recovers(client, emma, sarah):
    collection = client.post("/api/v1/knowledge/collections", json={
        "name": "Travel and interview guidance",
    }, headers=sarah).json()
    source = client.post(f"/api/v1/knowledge/collections/{collection['id']}/sources", json={
        "name": "guide.txt",
        "content": "A practical guide to preparing a structured interview and checklist.",
        "freshness_policy": "stale_after_90d",
    }, headers=sarah).json()
    version = client.post(
        f"/api/v1/knowledge/collections/{collection['id']}/versions", json={}, headers=sarah
    ).json()

    with SessionLocal() as db:
        from app.modules.identity.service import IdentityService
        from app.modules.profile.service import ProfileService

        sarah_user = IdentityService.get_by_email(db, "sarah@qora.ai")
        sarah_profile = ProfileService.get_creator_or_404(db, sarah_user.id)
        service = next(
            row for row in ServiceRegistry.list_by_creator(db, sarah_profile.id)
            if row.name == "Interview Coach"
        )
        active_version = ServiceRegistry.current_version(db, service)
        active_version.knowledge_config = {"knowledge_version_id": version["id"]}
        material = db.get(KnowledgeSource, source["id"])
        material.last_verified_at = datetime.now(timezone.utc) - timedelta(days=120)
        material.expires_at = datetime.now(timezone.utc) - timedelta(days=30)
        db.commit()
        service_id = service.id

    discovered = client.get("/api/v1/services", headers=emma).json()
    item = next(row for row in discovered if row["service"]["id"] == service_id)
    assert item["trust"]["freshness"] == "stale"
    assert item["rank"]["signals"]["freshness"] == 0.0
    assert item["trust"]["components"]["freshness"] == 0.0

    verified = client.post(f"/api/v1/knowledge/sources/{source['id']}/verify", headers=sarah)
    assert verified.status_code == 200
    assert verified.json()["fresh"] is True
    refreshed = client.get("/api/v1/services", headers=emma).json()
    item = next(row for row in refreshed if row["service"]["id"] == service_id)
    assert item["trust"]["freshness"] == "fresh"
    assert item["rank"]["signals"]["freshness"] == 1.0
    assert item["trust"]["components"]["freshness"] == 1.0
