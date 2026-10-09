"""P1-2 · Permission engine: ALLOW_ONCE semantics + least-context + audit."""


def _fresh_user(client):
    r = client.post("/api/v1/auth/register", json={
        "email": f"perm.{__import__('uuid').uuid4().hex[:6]}@example.com",
        "password": "secret123", "display_name": "Perm Tester", "roles_wanted": ["consumer"],
    })
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_allow_once_consumed(client):
    h = _fresh_user(client)  # isolated: no pre-existing grants
    conv = client.post("/api/v1/conversations", headers=h).json()
    r = client.post(f"/api/v1/conversations/{conv['id']}/messages", json={
        "content": "Help me prepare for a Product Manager interview next week"
    }, headers=h).json()
    assert "permission_request" in r["message"]["content_blocks"]
    svc_id = r["service_match"]["chosen_service_id"]

    g = client.post("/api/v1/permissions/grants", json={
        "service_id": svc_id, "context_type": "career", "mode": "ALLOW_ONCE",
    }, headers=h).json()
    assert g["mode"] == "ALLOW_ONCE"

    # first use consumes the grant → service runs
    r2 = client.post(f"/api/v1/conversations/{conv['id']}/messages", json={
        "content": "Help me prepare for a Product Manager interview next week"
    }, headers=h).json()
    assert r2["service_response"]["ok"] is True

    # ALLOW_ONCE is consumed → permission asked again for the same need
    r3 = client.post(f"/api/v1/conversations/{conv['id']}/messages", json={
        "content": "Help me prepare for a Product Manager interview next week"
    }, headers=h).json()
    assert "permission_request" in r3["message"]["content_blocks"]


def test_deny_grant_blocks_context(client, emma):
    conv = client.post("/api/v1/conversations", headers=emma).json()
    r = client.post(f"/api/v1/conversations/{conv['id']}/messages", json={
        "content": "Plan my trip next week to Rome"
    }, headers=emma).json()
    svc_id = r["service_match"]["chosen_service_id"]
    client.post("/api/v1/permissions/grants", json={
        "service_id": svc_id, "context_type": "travel", "mode": "DENY",
    }, headers=emma).json()
    r2 = client.post(f"/api/v1/conversations/{conv['id']}/messages", json={
        "content": "Plan my trip next week to Rome"
    }, headers=emma).json()
    # DENY → service must not receive context; either blocked for permission or context empty
    assert r2["context_shared"] == {} or "permission_request" in r2["message"]["content_blocks"]


def test_audit_lists_grants(client, emma):
    audit = client.get("/api/v1/permissions/audit", headers=emma).json()
    assert "items" in audit
