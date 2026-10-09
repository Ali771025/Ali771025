"""P1-7 · The MVP loop end-to-end (PHASING.md Phase-1 exit criteria)."""


def test_mvp_loop_exit_criteria(client, emma, sarah):
    text = "Next week I have an English interview for a Product Manager position"

    # 1. intent is structured [PRD]
    i = client.post("/api/v1/intents/analyze", json={"text": text}, headers=emma).json()
    assert i["primary_intent"] == "job_interview_preparation"
    assert i["entities"].get("Role") == "Product Manager"
    assert i["entities"].get("Date") == "next week"
    assert "interview_coaching" in i["required_capabilities"]

    # 2. discovery ranks the followed service first (personal fit)
    d = client.get("/api/v1/services?intent=job_interview_preparation", headers=emma).json()
    top = d[0]
    assert top["service"]["name"] == "Interview Coach"
    assert top["followed"] is True  # Emma follows it in the seed
    assert set(top["rank"]["signals"].keys()) >= {
        "intent_relevance", "outcome_quality", "personal_fit", "trust", "freshness", "satisfaction", "exploration",
    }

    # 3. conversation → permission request first
    conv = client.post("/api/v1/conversations", headers=emma).json()
    r = client.post(f"/api/v1/conversations/{conv['id']}/messages", json={"content": text}, headers=emma).json()
    assert "permission_request" in r["message"]["content_blocks"]

    # 4. grant → service runs → outcome SUCCESS
    client.post("/api/v1/permissions/grants", json={
        "service_id": r["service_match"]["chosen_service_id"], "context_type": "career", "mode": "ALWAYS_ALLOW",
    }, headers=emma).json()
    r2 = client.post(f"/api/v1/conversations/{conv['id']}/messages", json={"content": text}, headers=emma).json()
    assert r2["service_response"]["ok"] is True
    assert r2["outcome"]["status"] in ("SUCCESS", "PARTIAL")
    assert r2["outcome"]["user_confirmation_required"] is True

    # 5. outcome confirmation is structured, not a like
    oc = client.post(f"/api/v1/sessions/{r2['outcome']['session_id']}/outcome/confirm", json={
        "useful": True, "achieved_goal": True, "notes": "helpful",
    }, headers=emma).json()
    assert oc["user_confirmed"] is True

    # 6. Personal QORA learned: journey state + goal memory
    ctx = client.get("/api/v1/me/context", headers=emma).json()
    kinds = {m["kind"] for m in ctx["memories"]}
    assert "goal" in kinds
    journeys = {j["kind"]: j["state"] for j in ctx["journeys"]}
    assert "job_interview_preparation" in journeys

    # 7. full trace exists
    tr = client.get(f"/api/v1/conversations/{conv['id']}/trace/{r2['trace_id']}", headers=emma).json()
    assert tr["intent"]["slug"] == "job_interview_preparation"
    assert tr["outcome_status"] in ("SUCCESS", "PARTIAL")
    assert tr["chosen_service_version_id"]

    # 8. creator earned rewards from the useful outcome [PRD]
    rw = client.get("/api/v1/rewards/me", headers=sarah).json()
    assert rw["balance_units"] > 0
    assert any(e["direction"] == "CREDIT" for e in rw["ledger"])


def test_recovery_options(client, emma):
    conv = client.post("/api/v1/conversations", headers=emma).json()
    r = client.post(f"/api/v1/conversations/{conv['id']}/recovery", json={"option": "continue_with_qora"}, headers=emma).json()
    assert r["recovery_state"] == "normal"
