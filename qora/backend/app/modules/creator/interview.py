"""Creator Interview Engine + Service Specification Generator [PRD].

Philosophy: Conversation over Configuration — never a 40-field form.
Flow: intent statement → gap detection → targeted questions → auto-drafted spec
→ creator reviews TRUTH and key fixes only.
"""
import re

# Gap categories → questions. Gaps not detected from the statement are asked [ARCHITECTURE §4.19].
QUESTIONS = {
    "purpose": {
        "id": "q_purpose",
        "text": "Let's sharpen it: what should people be able to DO with this service? (one sentence)",
    },
    "audience": {
        "id": "q_audience",
        "text": "Who is this for? (e.g. beginners, professionals, students — and any level limits)",
    },
    "method": {
        "id": "q_method",
        "text": "What is YOUR method or approach? What makes the way you do it distinctive?",
    },
    "boundaries": {
        "id": "q_boundaries",
        "text": "What should this service REFUSE or never do? (negative boundaries)",
    },
    "outcome": {
        "id": "q_outcome",
        "text": "What does success look like? What concrete thing does the user walk away with?",
    },
    "knowledge": {
        "id": "q_knowledge",
        "text": "Should the service use your own training material? (yes/no — we'll set it up next)",
    },
    "risk": {
        "id": "q_risk",
        "text": "Does this touch sensitive areas (health, money, legal)? (yes/no)",
    },
}

GAP_MARKERS = {
    "audience": r"\b(for|aimed at|targeting)\s+(beginners|professionals|students|teams|companies|freelancers|developers|founders)\b",
    "method": r"\b(my method|our approach|using (my|our)|framework|step[- ]by[- ]step|unique)\b",
    "boundaries": r"\b(never|won't|does not|refuse|excluding|not for|no )\b",
    "outcome": r"\b(walk away with|deliverable|end (up )?with|outcome|result(ing)? in|checklist|plan|report)\b",
    "knowledge": r"\b(my (training|course|docs|material|playbook)|from my)\b",
    "risk": r"\b(health|medical|finance|financial|legal|investment|tax|therapy)\b",
}


def detect_gaps(statement: str) -> list[str]:
    low = statement.lower()
    gaps = []
    if len(statement.strip()) < 40:
        gaps.append("purpose")
    for gap, pattern in GAP_MARKERS.items():
        if not re.search(pattern, low):
            gaps.append(gap)
    return gaps


def next_question(gaps: list[str], answered: dict) -> dict | None:
    order = ["purpose", "audience", "method", "boundaries", "outcome", "knowledge", "risk"]
    for gap in order:
        if gap in gaps and QUESTIONS[gap]["id"] not in answered:
            return {"gap": gap, **QUESTIONS[gap]}
    return None


def generate_spec(statement: str, answers: dict, name_hint: str = "") -> dict:
    """Draft a ServiceSpecification from the interview [ARCHITECTURE §4.20]."""
    purpose = answers.get("q_purpose") or statement.strip()
    audience = answers.get("q_audience", "").strip() or "general users"
    method = answers.get("q_method", "").strip() or "guided step-by-step conversation"
    boundaries = answers.get("q_boundaries", "").strip() or "Stays strictly inside the stated purpose. No harmful, illegal or out-of-scope requests."
    outcome_text = answers.get("q_outcome", "").strip() or f"A concrete result: {purpose[:80]}"
    wants_knowledge = answers.get("q_knowledge", "").strip().lower().startswith("y")
    touches_risk = answers.get("q_risk", "").strip().lower().startswith("y")

    risk = "MEDIUM"
    blob = (statement + " " + purpose + " " + audience).lower()
    if touches_risk or re.search(r"\b(health|medical|finance|investment|legal|tax|therapy)\b", blob):
        risk = "HIGH"
    elif re.search(r"\b(career|coach|education|tutor|interviews?|business advice)\b", blob):
        risk = "MEDIUM"
    else:
        risk = "LOW"

    # name from the statement's first clause
    name = name_hint or (statement.strip().split(".")[0][:60] if statement.strip() else "New AI Service")
    name = re.sub(r"^(i want (to )?(help (people )?(to )?)|help (people )?(to )?)", "", name, flags=re.I).strip() or name
    name = name[:1].upper() + name[1:] if name else "New AI Service"

    return {
        "name": name,
        "summary": purpose[:220],
        "description": f"{purpose}\n\nHow it works: {method}\n\nWho it's for: {audience}",
        "purpose": purpose,
        "audience": audience,
        "method": method,
        "behavior": "friendly, concrete, stays inside boundaries; asks clarifying questions when the request is vague",
        "system_instructions": (
            f"You are {name}. Purpose: {purpose}. Audience: {audience}. "
            f"Method: {method}. Stay strictly inside this role. "
            f"Refuse requests that violate your boundaries. Ask a clarifying question when unclear."
        ),
        "boundaries": boundaries,
        "outcome_definition": {
            "text": outcome_text,
            "signals": ["relevant_interaction", "deliverable_generated", "plan_produced"],
        },
        "knowledge_requirements": "attach training material later" if wants_knowledge else "none",
        "knowledge_version_id": None,
        "capabilities": ["feedback", "explanation"],
        "examples": [{"input": statement[:100], "output": "produces the declared deliverable"}],
        "risk_classification": risk,
    }
