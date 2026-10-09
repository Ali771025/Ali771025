"""Small deterministic evaluation harness; no external model or network is required."""
from app.modules.intent.service import RuleIntentProvider
from app.modules.outcome.service import composite_score, status_for_score

INTENT_CASES = [
    {"text": "Next week I have an English interview for a Product Manager position", "expected": "job_interview_preparation"},
    {"text": "Plan a budget-friendly trip to Lisbon for next month", "expected": "trip_planning"},
    {"text": "Please edit my resume for a product role", "expected": "writing_editing"},
    {"text": "Help me validate my startup idea before building an MVP", "expected": "startup_idea_validation"},
    {"text": "Help me study for my physics exam", "expected": "learning_tutoring"},
    {"text": "I need English speaking practice to improve fluency", "expected": "english_speaking_practice"},
    {"text": "برای مصاحبه شغلی آماده‌ام کن", "expected": "job_interview_preparation"},
    {"text": "Can you proofread this cover letter", "expected": "writing_editing"},
    {"text": "I want a day-by-day holiday itinerary", "expected": "trip_planning"},
    {"text": "Explain calculus and give me practice questions", "expected": "learning_tutoring"},
]

OUTCOME_CASES = [
    {
        "name": "no useful work",
        "signals": {"service": 0.0, "completion": 0.0, "structured": 0.0, "confirmation": None, "followup": None},
        "expected": "FAILED",
    },
    {
        "name": "provisional partial result",
        "signals": {"service": 1.0, "completion": 0.5, "structured": 0.5, "confirmation": None, "followup": None},
        "expected": "PARTIAL",
    },
    {
        "name": "confirmed useful deliverable",
        "signals": {
            "service": 1.0,
            "completion": 1.0,
            "structured": 1.0,
            "confirmation": {"useful": 1.0, "achieved_goal": 1.0},
            "followup": None,
        },
        "expected": "SUCCESS",
    },
    {
        "name": "negative structured feedback",
        "signals": {
            "service": 1.0,
            "completion": 0.5,
            "structured": 0.5,
            "confirmation": {"useful": 0.0, "achieved_goal": 0.0},
            "followup": None,
        },
        "expected": "PARTIAL",
    },
]


def run_evaluation() -> dict:
    provider = RuleIntentProvider()
    intent_rows = []
    for case in INTENT_CASES:
        raw = provider.analyze(case["text"])
        actual = raw["primary"] if raw else "general_assistance"
        intent_rows.append({"expected": case["expected"], "actual": actual, "passed": actual == case["expected"]})
    outcome_rows = []
    for case in OUTCOME_CASES:
        score = composite_score(case["signals"])
        actual = status_for_score(score)
        outcome_rows.append({
            "name": case["name"],
            "score": score,
            "expected": case["expected"],
            "actual": actual,
            "passed": actual == case["expected"],
        })
    return {
        "intent": {
            "cases": len(intent_rows),
            "passed": sum(row["passed"] for row in intent_rows),
            "accuracy": round(sum(row["passed"] for row in intent_rows) / max(len(intent_rows), 1), 3),
            "results": intent_rows,
        },
        "outcome": {
            "cases": len(outcome_rows),
            "passed": sum(row["passed"] for row in outcome_rows),
            "results": outcome_rows,
        },
    }
