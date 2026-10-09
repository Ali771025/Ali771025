"""P0-2 · Identity: register/login/refresh/sessions."""


def test_register_login_me(client):
    r = client.post("/api/v1/auth/register", json={
        "email": "new.user@example.com", "password": "secret123",
        "display_name": "New User", "roles_wanted": ["consumer", "creator"],
    })
    assert r.status_code == 201
    tok = r.json()
    assert tok["access_token"] and tok["refresh_token"]
    h = {"Authorization": "Bearer " + tok["access_token"]}
    me = client.get("/api/v1/me", headers=h).json()
    assert me["email"] == "new.user@example.com"
    assert "creator" in me["roles"]  # [PRD] one user, many hats

    # private profile auto-created
    p = client.get("/api/v1/me/profile/private", headers=h).json()
    assert p["display_name"] == "New User"

    # refresh rotates
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": tok["refresh_token"]})
    assert r2.status_code == 200
    assert r2.json()["refresh_token"] != tok["refresh_token"]

    # old refresh is revoked after rotation
    r3 = client.post("/api/v1/auth/refresh", json={"refresh_token": tok["refresh_token"]})
    assert r3.status_code == 401


def test_duplicate_email_conflict(client):
    r = client.post("/api/v1/auth/register", json={
        "email": "emma@qora.ai", "password": "secret123", "display_name": "Dup", "roles_wanted": ["consumer"],
    })
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "CONFLICT"


def test_error_envelope_shape(client):
    r = client.post("/api/v1/auth/login", json={"email": "emma@qora.ai", "password": "wrong"})
    assert r.status_code == 401
    body = r.json()["error"]
    assert body["code"] == "UNAUTHENTICATED"
    assert "trace_id" in body
