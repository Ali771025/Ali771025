"""Model Gateway [TECH] — services declare *capabilities*, never providers.

Adapters: LocalDeterministic (offline default) · OpenAICompatible (opt-in).
"""
import time
from abc import ABC, abstractmethod

from app.core.config import settings


class ModelAdapter(ABC):
    name = "abstract"

    @abstractmethod
    def invoke(self, system: str, user_message: str, needs: dict, context: dict) -> dict:
        """Returns {content, deliverable, prompt_tokens, completion_tokens, latency_ms, cost_usd}."""
        ...


class LocalDeterministicAdapter(ModelAdapter):
    """Offline capability-satisfying adapter — makes every demo/test reproducible [TECH]."""

    name = "local"

    TEMPLATES = {
        "interview": (
            "Let's practice for your {role} interview.\n\n"
            "Question 1 (behavioral): Tell me about a time you had to prioritize competing deadlines.\n\n"
            "I'll score your answer on structure (STAR), role relevance and clarity — just reply naturally.\n\n"
            "Practice plan:\n1. Warm-up: your background in 60 seconds\n"
            "2. 3 behavioral questions (STAR)\n3. 2 role-specific case questions\n4. Feedback + improvement checklist"
        ),
        "trip": (
            "Here's a draft itinerary for your {date} trip:\n\n"
            "Day 1 — arrival, neighborhood walk, local dinner\n"
            "Day 2 — main attraction in the morning, museum/café afternoon\n"
            "Day 3 — day trip, evening free\n\n"
            "Tell me your budget and priorities (food, nature, culture) and I'll refine it into a usable plan."
        ),
        "startup": (
            "Let's validate your idea step by step:\n\n"
            "1. Problem: who feels this pain today, and how do they cope?\n"
            "2. Solution test: what's the smallest experiment you can run this week?\n"
            "3. Market: 3 comparable products and their pricing\n\n"
            "Answer question 1 and I'll generate a validation checklist with pass/fail criteria."
        ),
        "writing": (
            "Happy to edit your text. Paste the draft and tell me the audience.\n\n"
            "You'll get:\n1. A corrected version (grammar, flow)\n2. Tone suggestions\n"
            "3. A short rationale for the 3 biggest changes.\n\n"
            "Deliverable: revised text + change rationale."
        ),
        "generic": (
            "I can help with that. Here's a structured starting point:\n\n"
            "1. Clarify the goal and constraints\n2. Break the work into 3 steps\n"
            "3. Deliver a concrete first draft you can react to.\n\n"
            "Tell me a bit more about the outcome you want and I'll tailor it."
        ),
    }

    def _pick(self, service_name: str, purpose: str) -> str:
        blob = (service_name + " " + purpose).lower()
        for key in ("interview", "trip", "startup", "writing"):
            if key in blob:
                return key
        return "generic"

    def invoke(self, system: str, user_message: str, needs: dict, context: dict) -> dict:
        t0 = time.time()
        if "SIMULATE_FAILURE" in (system or ""):
            raise RuntimeError("MODEL_FAILURE:simulated")
        key = self._pick(context.get("service_name", ""), context.get("purpose", ""))
        role = context.get("entities", {}).get("Role", "the target")
        date = context.get("entities", {}).get("Date", "your dates")
        content = self.TEMPLATES[key].format(role=role, date=date)
        latency = int((time.time() - t0) * 1000) + 12
        return {
            "content": content,
            "deliverable": {"kind": key, "status": "draft"},
            "prompt_tokens": len(user_message.split()) * 2,
            "completion_tokens": len(content.split()) * 2,
            "latency_ms": latency,
            "cost_usd": 0.0,
        }


class OpenAICompatibleAdapter(ModelAdapter):
    """Real providers plug in here — routing is by capability, not brand [PRD concept]."""

    name = "openai_compatible"

    def invoke(self, system: str, user_message: str, needs: dict, context: dict) -> dict:
        import httpx

        t0 = time.time()
        r = httpx.post(
            settings.OPENAI_BASE_URL.rstrip("/") + "/chat/completions",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            json={
                "model": settings.OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
            },
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return {
            "content": content,
            "deliverable": {"kind": "text", "status": "draft"},
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "latency_ms": int((time.time() - t0) * 1000),
            "cost_usd": 0.0,
        }


class ModelGateway:
    """Router: capability + cost + latency + availability + policy [TECH]."""

    @staticmethod
    def select(needs: dict) -> ModelAdapter:
        if settings.MODEL_PROVIDER == "openai_compatible" and settings.OPENAI_API_KEY:
            return OpenAICompatibleAdapter()
        return LocalDeterministicAdapter()

    @staticmethod
    def invoke(system: str, user_message: str, needs: dict, context: dict) -> dict:
        adapter = ModelGateway.select(needs)
        result = adapter.invoke(system, user_message, needs, context)
        result["provider"] = adapter.name
        result["model"] = settings.OPENAI_MODEL if adapter.name != "local" else "qora-local-v1"
        return result

    @staticmethod
    def invoke_with_fallback(system: str, user_message: str, needs: dict, context: dict) -> dict:
        """Try the configured model first, then the independent local model [Phase 3]."""
        primary = ModelGateway.select(needs)
        try:
            result = primary.invoke(system, user_message, needs, context)
            result["provider"] = primary.name
            result["model"] = settings.OPENAI_MODEL if primary.name != "local" else "qora-local-v1"
            result["fallback_used"] = False
            return result
        except Exception as primary_error:
            if primary.name == "local":
                raise
            fallback = LocalDeterministicAdapter()
            try:
                result = fallback.invoke(system, user_message, needs, context)
                result["provider"] = fallback.name
                result["model"] = "qora-local-v1"
                result["fallback_used"] = True
                result["fallback_reason"] = type(primary_error).__name__
                return result
            except Exception as fallback_error:
                raise RuntimeError(
                    f"Primary and fallback models failed ({type(primary_error).__name__}; "
                    f"{type(fallback_error).__name__})"
                ) from fallback_error
