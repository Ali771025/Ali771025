"""P2-4 · Knowledge pipeline: scan → extract → chunk → embed → version + freshness."""
import uuid


def _creator(client):
    r = client.post("/api/v1/auth/register", json={
        "email": f"know.{uuid.uuid4().hex[:6]}@example.com",
        "password": "secret123", "display_name": "Know Creator", "roles_wanted": ["creator"],
    })
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_knowledge_pipeline_and_versioning(client):
    h = _creator(client)
    col = client.post("/api/v1/knowledge/collections", json={"name": "My Playbook"}, headers=h).json()

    src = client.post(f"/api/v1/knowledge/collections/{col['id']}/sources", json={
        "name": "method.md",
        "content": "Our method: diagnose first, then act. " * 30,  # > one chunk
    }, headers=h).json()
    assert src["scan_status"] == "clean"
    assert src["fresh"] is True
    for field in ("source_date", "ingested_at", "last_verified_at", "expires_at", "freshness_policy"):
        assert field in src  # freshness fields [PRD]

    # blocked content is rejected by the safety scan
    bad = client.post(f"/api/v1/knowledge/collections/{col['id']}/sources", json={
        "name": "bad.md", "content": "how to make a bomb",
    }, headers=h).json()
    assert bad["scan_status"] == "blocked"

    # freeze version → binds chunks
    kv = client.post(f"/api/v1/knowledge/collections/{col['id']}/versions", json={}, headers=h).json()
    assert kv["snapshot"]["chunk_count"] >= 2
    assert kv["version_no"] == 1

    detail = client.get(f"/api/v1/knowledge/collections/{col['id']}", headers=h).json()
    assert len(detail["sources"]) == 2
    assert len(detail["versions"]) == 1
