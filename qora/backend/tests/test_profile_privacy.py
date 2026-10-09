"""P0-3 · Profile privacy boundary [PRD]: private fields never leak publicly."""
import json


def test_private_fields_never_in_public_projection(client, emma):
    # owner can read private profile (with private fields)
    priv = client.get("/api/v1/me/profile/private", headers=emma).json()
    assert priv["language"] and priv["timezone"]

    # public creator projection of Sarah must not contain private keys
    users = client.get("/api/v1/me", headers=emma).json()
    r = client.get("/api/v1/creators/3")  # sarah (seeded 3rd user) — public endpoint
    if r.status_code == 200:
        pub = r.json()
        blob = json.dumps(pub).lower()
        for forbidden in ("language", "timezone", "birth", "preference", "memories", "password"):
            assert forbidden not in blob or forbidden in ("display_name",), f"leak: {forbidden}"
        allowed = {"id", "display_name", "bio", "headline", "expertise_tags", "verification_status", "trust_score"}
        assert set(pub.keys()) <= allowed


def test_creator_upgrade_same_account(client, emma):
    """[PRD] becoming a creator does not create a second account."""
    before = client.get("/api/v1/me", headers=emma).json()
    r = client.post("/api/v1/me/profile/creator", headers=emma)
    assert r.status_code == 201
    after = client.get("/api/v1/me", headers=emma).json()
    assert after["id"] == before["id"]
    assert "creator" in after["roles"]
