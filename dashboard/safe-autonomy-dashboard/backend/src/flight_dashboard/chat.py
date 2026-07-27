from __future__ import annotations

import json
import re
import uuid
from typing import Any

import httpx

from .database import Database
from .models import AdvisoryAction, ChatResponse, Severity
from .settings import Settings


FORBIDDEN_COMMAND_PATTERNS = [
    r"\b(vehicle_command|actuator|motor|setpoint|waypoint|mavlink)\b",
    r"\b(lat|latitude|lon|longitude)\s*[:=]\s*-?\d",
    r"\b(channel|pwm)\s*[:=]\s*\d",
]


SYSTEM_PROMPT = """شما دستیار مشورتی عملیات پرواز هستید. فقط وضعیت را خلاصه و ریسک را توضیح بدهید.
هیچ فرمان کنترلی، مختصات، setpoint، waypoint، PWM، MAVLink یا دستور موتور تولید نکنید.
خروجی فقط JSON با کلیدهای answer، risk_level، suggested_action، evidence_ids باشد.
risk_level یکی از INFO/WARNING/CRITICAL و suggested_action فقط یکی از
CONTINUE/REQUEST_SENSOR_UPDATE/REQUEST_REPLAN/HOLD/RETURN/LAND/ABSTAIN است.
اگر شواهد کافی نیست ABSTAIN را انتخاب کنید. پاسخ فارسی و کوتاه باشد."""


def _safe_response(raw: dict[str, Any], conversation_id: str, model: str) -> ChatResponse:
    answer = str(raw.get("answer", "به دلیل نبود شواهد کافی، تصمیم‌گیری خودکار انجام نشد."))[:3000]
    serialized = json.dumps(raw, ensure_ascii=False)
    if any(re.search(pattern, serialized, flags=re.IGNORECASE) for pattern in FORBIDDEN_COMMAND_PATTERNS):
        return ChatResponse(
            conversation_id=conversation_id,
            answer="پاسخ مدل شامل محتوای کنترلی غیرمجاز بود و مسدود شد. بررسی انسانی لازم است.",
            risk_level=Severity.WARNING,
            suggested_action=AdvisoryAction.ABSTAIN,
            evidence_ids=[],
            model=f"{model}:safety-gate",
        )
    try:
        risk = Severity(raw.get("risk_level", "INFO"))
        action = AdvisoryAction(raw.get("suggested_action", "ABSTAIN"))
    except ValueError:
        risk, action = Severity.WARNING, AdvisoryAction.ABSTAIN
    evidence = [str(item)[:128] for item in raw.get("evidence_ids", []) if isinstance(item, (str, int))][:12]
    return ChatResponse(
        conversation_id=conversation_id,
        answer=answer,
        risk_level=risk,
        suggested_action=action,
        evidence_ids=evidence,
        model=model,
    )


class AdvisoryService:
    def __init__(self, settings: Settings, database: Database):
        self.settings = settings
        self.database = database

    async def ask(self, username: str, conversation_id: str | None, message: str, context: dict) -> ChatResponse:
        conversation_id = conversation_id or str(uuid.uuid4())
        self._save(conversation_id, username, "user", message, {})
        compact_context = json.dumps(context, ensure_ascii=False, separators=(",", ":"))[:14_000]
        model = self.settings.ollama_model
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                response = await client.post(
                    f"{self.settings.ollama_url.rstrip('/')}/api/chat",
                    json={
                        "model": model,
                        "stream": False,
                        "format": "json",
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": f"وضعیت زنده: {compact_context}\nپرسش: {message}"},
                        ],
                    },
                )
                response.raise_for_status()
                content = response.json()["message"]["content"]
                raw = json.loads(content)
        except (httpx.HTTPError, KeyError, json.JSONDecodeError, TypeError):
            raw = self._fallback(message, context)
            model = "deterministic-fallback"
        result = _safe_response(raw, conversation_id, model)
        self._save(conversation_id, username, "assistant", result.answer, result.model_dump(mode="json"))
        self.database.audit(username, "CHAT_ADVISORY", "conversation", conversation_id, {"model": result.model})
        return result

    def _fallback(self, message: str, context: dict) -> dict[str, Any]:
        telemetry = context.get("topics", {}).get("telemetry", {}).get("payload", {})
        battery = float(telemetry.get("battery_percent", 100))
        gps_fix = int(telemetry.get("gps_fix", 3))
        link = float(telemetry.get("link_quality", 100))
        if battery < 20 or gps_fix < 3 or link < 25:
            return {
                "answer": f"ریسک عملیاتی بالاست: باتری {battery:.0f}٪، وضعیت GPS برابر {gps_fix} و کیفیت لینک {link:.0f}٪ است. تأیید کارشناس پرواز لازم است.",
                "risk_level": "CRITICAL" if battery < 12 or link < 12 else "WARNING",
                "suggested_action": "HOLD",
                "evidence_ids": ["telemetry.latest"],
            }
        return {
            "answer": "پارامترهای اصلی دریافت‌شده در محدوده عادی هستند. این جمع‌بندی مشورتی است و تصمیم با تیم پرواز باقی می‌ماند.",
            "risk_level": "INFO",
            "suggested_action": "CONTINUE",
            "evidence_ids": ["telemetry.latest"],
        }

    def _save(self, conversation_id: str, username: str, role: str, content: str, metadata: dict) -> None:
        import time

        self.database.execute(
            "INSERT INTO chat_messages VALUES (?,?,?,?,?,?,?)",
            (
                str(uuid.uuid4()),
                conversation_id,
                username,
                role,
                content,
                json.dumps(metadata, ensure_ascii=False),
                int(time.time() * 1000),
            ),
        )
