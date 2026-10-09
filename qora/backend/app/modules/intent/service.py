"""Intent Engine v1 [PRD] — detection, decomposition, entities, ambiguity, capability mapping.

Hybrid: deterministic rules always work offline; an LLM provider can be plugged in
behind `LLMIntentProvider` without touching callers [TECH].
"""
import re
from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.intent.models import Capability, Intent, IntentCapability, UserIntentHistory
from app.modules.intent.schemas import IntentResult

# rule table: slug -> keyword patterns (word-ish matching)
RULES: dict[str, list[str]] = {
    "job_interview_preparation": [
        r"interview", r"job (interview|application)", r"hiring", r"recruit",
        r"مصاحبه", r"product manager", r"\bpm position\b",
    ],
    "english_speaking_practice": [
        r"english", r"speaking", r"speaking practice", r"fluency", r"accent",
    ],
    "trip_planning": [
        r"trip", r"travel", r"itinerary", r"vacation", r"holiday", r"hotel", r"flight",
    ],
    "startup_idea_validation": [
        r"startup", r"idea validation", r"validate (my )?idea", r"business idea", r"mvp",
    ],
    "writing_editing": [
        r"writ(e|ing)", r"edit(ing)?", r"proofread", r"blog (post|article)", r"resume", r"cover letter",
    ],
    "learning_tutoring": [
        r"learn", r"study", r"tutor", r"course", r"exam", r"math", r"physics", r"calculus", r"algebra",
    ],
}

SECONDARY_HINTS = {
    "english_speaking_practice": [r"english", r"انگلیسی"],
}

INTENT_CAPABILITIES = {
    "job_interview_preparation": ["interview_coaching", "feedback", "role_specific_prep"],
    "english_speaking_practice": ["english_practice", "conversation", "feedback"],
    "trip_planning": ["itinerary_planning", "recommendation"],
    "startup_idea_validation": ["idea_critique", "market_analysis"],
    "writing_editing": ["text_improvement", "proofreading"],
    "learning_tutoring": ["explanation", "practice_questions"],
}


class IntentProvider(ABC):
    @abstractmethod
    def analyze(self, text: str) -> dict | None:  # {"primary":..., "confidence":..., "entities":...}
        ...


class RuleIntentProvider(IntentProvider):
    """Deterministic fallback — always available offline [TECH]."""

    def analyze(self, text: str) -> dict | None:
        low = text.lower()
        scores: dict[str, float] = {}
        for slug, pats in RULES.items():
            hits = sum(1 for p in pats if re.search(p, low))
            if hits:
                scores[slug] = min(0.55 + 0.15 * hits, 0.97)
        if not scores:
            return None
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        primary, conf = ranked[0]
        return {
            "primary": primary,
            "confidence": conf,
            "runner_up": ranked[1][0] if len(ranked) > 1 and conf - ranked[1][1] < 0.12 else None,
            "entities": extract_entities(text),
        }


class LLMIntentProvider(IntentProvider):
    """OpenAI-compatible provider — enabled when MODEL_PROVIDER=openai_compatible [TECH]."""

    def analyze(self, text: str) -> dict | None:
        try:
            import httpx

            r = httpx.post(
                settings.OPENAI_BASE_URL.rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json={
                    "model": settings.OPENAI_MODEL,
                    "messages": [
                        {"role": "system", "content": "Classify the user intent into one of: " + ", ".join(RULES) + '. Reply JSON {"primary":..., "confidence":0..1}.'},
                        {"role": "user", "content": text},
                    ],
                    "temperature": 0,
                },
                timeout=15,
            )
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            import json as _json

            parsed = _json.loads(content)
            return {"primary": parsed["primary"], "confidence": float(parsed.get("confidence", 0.8)), "runner_up": None, "entities": extract_entities(text)}
        except Exception:
            return None  # graceful degradation to rules


def extract_entities(text: str) -> dict:
    entities: dict = {}
    m = re.search(r"for (?:a |an |the )?([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)?) (?:position|role|job|interview)", text)
    if m:
        entities["Role"] = m.group(1).strip()
    m = re.search(r"as (?:a |an )?([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)?)", text)
    if m and "Role" not in entities:
        entities["Role"] = m.group(1).strip()
    low = text.lower()
    if "next week" in low:
        entities["Date"] = "next week"
    elif "next month" in low:
        entities["Date"] = "next month"
    elif "tomorrow" in low:
        entities["Date"] = "tomorrow"
    if "english" in low:
        entities["Language"] = "English"
    m = re.search(r"\$?(\d{2,6})\s*(usd|dollars|\$)?\s*budget", low)
    if m:
        entities["Budget"] = m.group(1)
    return entities


class IntentService:
    @staticmethod
    def ids_for_slugs(db: Session, intent_slugs: list[str], cap_slugs: list[str]) -> dict[str, int]:
        """Interface helper: resolve slugs → ids without exposing models."""
        out: dict[str, int] = {}
        for slug in set(intent_slugs):
            row = db.scalar(select(Intent).where(Intent.slug == slug))
            if row:
                out[slug] = row.id
        for slug in set(cap_slugs):
            row = db.scalar(select(Capability).where(Capability.slug == slug))
            if row:
                out[slug] = row.id
        return out

    @staticmethod
    def _provider() -> IntentProvider:
        if settings.MODEL_PROVIDER == "openai_compatible" and settings.OPENAI_API_KEY:
            llm = LLMIntentProvider()
            return _HybridProvider(llm, RuleIntentProvider())
        return RuleIntentProvider()

    @staticmethod
    def analyze(db: Session, user_id: int, text: str, conversation_id: int | None = None) -> IntentResult:
        raw = IntentService._provider().analyze(text)
        if not raw:
            result = IntentResult(primary_intent="general_assistance", confidence=0.3, ambiguous=True, entities=extract_entities(text))
        else:
            secondary = []
            if raw.get("runner_up"):
                secondary.append(raw["runner_up"])
            low_text = text.lower()
            if raw["primary"] != "english_speaking_practice":
                for p in SECONDARY_HINTS["english_speaking_practice"]:
                    if re.search(p, low_text):
                        secondary.append("english_speaking_practice")
                        break
            # Coordinated goals become secondary intents for the multi-service planner.
            if re.search(r"\b(and|also|then|plus|as well as)\b", low_text):
                for slug, patterns in RULES.items():
                    if slug != raw["primary"] and any(re.search(pattern, low_text) for pattern in patterns):
                        secondary.append(slug)
            secondary = list(dict.fromkeys(slug for slug in secondary if slug != raw["primary"]))
            result = IntentResult(
                primary_intent=raw["primary"],
                secondary_intents=secondary,
                entities=raw.get("entities", {}),
                required_capabilities=INTENT_CAPABILITIES.get(raw["primary"], []),
                confidence=raw["confidence"],
                ambiguous=raw.get("runner_up") is not None and raw["confidence"] < 0.7,
            )
        # persist history [PRD: intent graph]
        intent = db.scalar(select(Intent).where(Intent.slug == result.primary_intent))
        if intent:
            db.add(UserIntentHistory(
                user_id=user_id, intent_id=intent.id, conversation_id=conversation_id,
                confidence=result.confidence, entities=result.entities,
            ))
            db.commit()
        return result

    @staticmethod
    def capabilities_for_intents(intent_slugs: list[str]) -> list[str]:
        """Interface for the orchestrator: union ordered capabilities across detected intents."""
        capabilities: list[str] = []
        for slug in intent_slugs:
            for capability in INTENT_CAPABILITIES.get(slug, []):
                if capability not in capabilities:
                    capabilities.append(capability)
        return capabilities

    @staticmethod
    def catalog(db: Session) -> list[dict]:
        caps = list(db.scalars(select(Capability)).all())
        cap_by_id = {c.id: c for c in caps}
        out = []
        for i in db.scalars(select(Intent)).all():
            linked = db.scalars(select(IntentCapability).where(IntentCapability.intent_id == i.id)).all()
            out.append({
                "slug": i.slug,
                "name": i.name,
                "description": i.description,
                "capabilities": [cap_by_id[l.capability_id].slug for l in linked if l.capability_id in cap_by_id],
            })
        return out


class _HybridProvider(IntentProvider):
    def __init__(self, primary: IntentProvider, fallback: IntentProvider):
        self.primary = primary
        self.fallback = fallback

    def analyze(self, text: str) -> dict | None:
        return self.primary.analyze(text) or self.fallback.analyze(text)
