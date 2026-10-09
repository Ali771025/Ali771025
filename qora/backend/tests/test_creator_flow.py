"""P2 · Creator Platform exit criteria: intent statement → qualified, published service."""
import uuid


def _creator(client):
    r = client.post("/api/v1/auth/register", json={
        "email": f"creator.{uuid.uuid4().hex[:6]}@example.com",
        "password": "secret123", "display_name": "Test Creator", "roles_wanted": ["consumer", "creator"],
    })
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_interview_detects_gaps_and_generates_spec(client):
    h = _creator(client)
    iv = client.post("/api/v1/creator/interviews", json={
        "intent_statement": "I want to help founders validate their startup ideas before they build"
    }, headers=h).json()
    assert iv["next_question"] is not None
    assert "audience" in iv["gaps_detected"]

    q = iv["next_question"]
    answers = {
        "q_purpose": "Stress-test a startup idea with a concrete validation checklist",
        "q_audience": "early-stage founders",
        "q_method": "problem-solution-market walkthrough with pass/fail criteria",
        "q_boundaries": "No investment advice. Never endorse a specific investor.",
        "q_outcome": "a validation checklist with pass/fail criteria",
        "q_knowledge": "no",
        "q_risk": "no",
    }
    while q:
        r = client.post(f"/api/v1/creator/interviews/{iv['id']}/answers", json={
            "answers": [{"question_id": q["id"], "text": answers.get(q["id"], "x")}]
        }, headers=h).json()
        q = r.get("next_question")

    assert r["interview_complete"] is True
    spec = r["spec_draft"]
    assert spec["purpose"] and spec["audience"] and spec["boundaries"]
    assert spec["outcome_definition"]["text"]
    assert spec["risk_classification"] in ("LOW", "MEDIUM", "HIGH")

    # truth review — creator fixes a fact
    fixed = client.patch(f"/api/v1/creator/interviews/{iv['id']}/spec", json={
        "audience": "first-time founders", "risk_classification": "MEDIUM",
    }, headers=h).json()
    assert fixed["audience"] == "first-time founders"


def test_simulation_and_qualification_and_publish(client):
    h = _creator(client)
    iv = client.post("/api/v1/creator/interviews", json={
        "intent_statement": "I want to help people plan calm, budget-friendly trips with day-by-day itineraries"
    }, headers=h).json()
    answers = {
        "q_purpose": "Produce a usable day-by-day itinerary",
        "q_audience": "travelers who want a concrete plan",
        "q_method": "dates + budget + priorities in, itinerary out",
        "q_boundaries": "No visa or legal advice. Prices are estimates only.",
        "q_outcome": "a usable itinerary covering dates, budget and priorities",
        "q_knowledge": "no",
        "q_risk": "no",
    }
    q = iv["next_question"]
    while q:
        r = client.post(f"/api/v1/creator/interviews/{iv['id']}/answers", json={
            "answers": [{"question_id": q["id"], "text": answers.get(q["id"], "x")}]
        }, headers=h).json()
        q = r.get("next_question")
    spec = r["spec_draft"]

    # 7-scenario simulation with per-case records
    sim = client.post(f"/api/v1/creator/interviews/{iv['id']}/simulate", headers=h).json()
    assert sim["summary"]["cases"] == 7
    assert set(sim["summary"]["per_kind"].keys()) == {"normal", "ambiguous", "edge", "boundary", "unsafe", "unsupported", "adversarial"}
    for res in sim["results"]:
        assert res["actual_behavior"] and 0 <= res["score"] <= 1

    # qualification: 6 PRD criteria + duplicate control
    qrun = client.post(f"/api/v1/creator/interviews/{iv['id']}/qualify", headers=h).json()
    criteria = {c["criterion"] for c in qrun["checks"]}
    assert {"specification", "outcome", "safety", "boundaries", "reliability", "differentiation", "knowledge"} <= criteria
    assert qrun["result"] in ("READY_TO_PUBLISH", "NEEDS_IMPROVEMENT", "RESTRICTED")
    # duplicate control returns a QUESTION, never a rejection
    for d in qrun["duplicates"]:
        assert d["question"]
        assert d["resolution"] in ("unique", "needs_differentiation", "merge_suggested")

    # publish walks the legal lifecycle path
    pub = client.post(f"/api/v1/creator/interviews/{iv['id']}/publish", json={"visibility": "public"}, headers=h).json()
    assert pub["service_id"]
    if qrun["result"] == "READY_TO_PUBLISH":
        assert pub["lifecycle_status"] == "published"

    # consumer can discover it
    d = client.get("/api/v1/services", headers=h).json()
    assert any(x["service"]["id"] == pub["service_id"] for x in d)


def test_creator_analytics(client):
    h = _creator(client)
    ov = client.get("/api/v1/creator/analytics/overview", headers=h).json()
    assert "totals" in ov and "per_service" in ov
