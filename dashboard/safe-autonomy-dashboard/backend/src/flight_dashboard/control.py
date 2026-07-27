from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from typing import Any

import httpx
from fastapi import HTTPException

from .auth import CurrentUser
from .database import Database
from .models import ControlAction, ControlIntentRequest, Role
from .settings import Settings


CRITICAL_ACTIONS = {
    ControlAction.ARM,
    ControlAction.TAKEOFF,
    ControlAction.RETURN_TO_HOME,
    ControlAction.LAND,
    ControlAction.ABORT_MISSION,
}


class ControlService:
    """Supervised high-level command workflow; never emits raw flight-controller messages."""

    def __init__(self, settings: Settings, database: Database, state_snapshot):
        self.settings = settings
        self.database = database
        self.state_snapshot = state_snapshot

    def create_intent(self, request: ControlIntentRequest, user: CurrentUser) -> dict[str, Any]:
        if self.settings.control_mode == "disabled":
            raise HTTPException(503, "درگاه کنترل غیرفعال است")
        existing = self.database.one("SELECT * FROM control_intents WHERE idempotency_key=?", (request.idempotency_key,))
        if existing:
            return existing
        self._check_preconditions(request.action)
        if self.settings.control_require_dual_approval and request.action in CRITICAL_ACTIONS and user.role != Role.FLIGHT_EXPERT:
            raise HTTPException(403, "درخواست فرمان بحرانی باید توسط کارشناس پرواز آغاز شود")
        now = int(time.time() * 1000)
        intent_id = str(uuid.uuid4())
        needs_approval = self.settings.control_require_dual_approval and request.action in CRITICAL_ACTIONS
        status = "PENDING_APPROVAL" if needs_approval else "APPROVED"
        self.database.execute(
            "INSERT INTO control_intents(id,idempotency_key,action,reason,status,requested_by,requested_role,created_at_ms,expires_at_ms) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                intent_id,
                request.idempotency_key,
                request.action.value,
                request.reason,
                status,
                user.username,
                user.role.value,
                now,
                now + self.settings.control_intent_ttl_seconds * 1000,
            ),
        )
        self.database.audit(user.username, "CONTROL_REQUEST", "control_intent", intent_id, {"action": request.action.value})
        intent = self.database.one("SELECT * FROM control_intents WHERE id=?", (intent_id,))
        return intent or {}

    async def approve(self, intent_id: str, note: str, user: CurrentUser) -> dict[str, Any]:
        if user.role != Role.FLIGHT_MANAGER:
            raise HTTPException(403, "تأیید فرمان بحرانی فقط با مدیر پرواز است")
        with self.database.transaction():
            intent = self.database.one("SELECT * FROM control_intents WHERE id=?", (intent_id,))
            if not intent:
                raise HTTPException(404, "درخواست کنترل یافت نشد")
            if intent["status"] != "PENDING_APPROVAL":
                raise HTTPException(409, "درخواست در وضعیت قابل تأیید نیست")
            if intent["requested_by"] == user.username:
                raise HTTPException(409, "درخواست‌کننده نمی‌تواند تأییدکننده همان فرمان باشد")
            if intent["expires_at_ms"] < int(time.time() * 1000):
                self.database.execute("UPDATE control_intents SET status='EXPIRED' WHERE id=?", (intent_id,))
                raise HTTPException(409, "مهلت تأیید منقضی شده است")
            updated = self.database.connection.execute(
                "UPDATE control_intents SET status='APPROVED',approved_by=?,approval_note=? WHERE id=? AND status='PENDING_APPROVAL'",
                (user.username, note, intent_id),
            )
            if updated.rowcount != 1:
                raise HTTPException(409, "درخواست پیش از این به‌روزرسانی شده است")
        self.database.audit(user.username, "CONTROL_APPROVE", "control_intent", intent_id, {})
        return await self.execute(intent_id)

    async def execute(self, intent_id: str) -> dict[str, Any]:
        with self.database.transaction():
            intent = self.database.one("SELECT * FROM control_intents WHERE id=?", (intent_id,))
            if not intent or intent["status"] != "APPROVED":
                raise HTTPException(409, "فرمان تأیید نشده است")
            self._check_preconditions(ControlAction(intent["action"]))
            if self.settings.control_mode == "simulation":
                result = {"accepted": True, "mode": "simulation", "detail": "فرمان فقط در شبیه‌ساز ثبت شد"}
            elif self.settings.control_mode == "gateway":
                result = await self._send_gateway(intent)
            else:
                raise HTTPException(503, "درگاه کنترل غیرفعال است")
            now = int(time.time() * 1000)
            updated = self.database.connection.execute(
                "UPDATE control_intents SET status='EXECUTED',executed_at_ms=?,result_json=? WHERE id=? AND status='APPROVED'",
                (now, json.dumps(result, ensure_ascii=False), intent_id),
            )
            if updated.rowcount != 1:
                raise HTTPException(409, "فرمان قبلاً اجرا یا لغو شده است")
        self.database.audit("system", "CONTROL_EXECUTE", "control_intent", intent_id, result)
        return self.database.one("SELECT * FROM control_intents WHERE id=?", (intent_id,)) or {}

    def cancel(self, intent_id: str, user: CurrentUser) -> dict[str, Any]:
        with self.database.transaction():
            intent = self.database.one("SELECT * FROM control_intents WHERE id=?", (intent_id,))
            if not intent:
                raise HTTPException(404, "درخواست یافت نشد")
            if intent["status"] in {"EXECUTED", "CANCELLED"}:
                raise HTTPException(409, "درخواست قابل لغو نیست")
            if intent["status"] == "PENDING_APPROVAL" and user.username != intent["requested_by"] and user.role != Role.FLIGHT_MANAGER:
                raise HTTPException(403, "فقط درخواست‌کننده یا مدیر پرواز می‌تواند درخواست را لغو کند")
            if intent["expires_at_ms"] < int(time.time() * 1000):
                self.database.execute("UPDATE control_intents SET status='EXPIRED' WHERE id=?", (intent_id,))
                raise HTTPException(409, "مهلت درخواست منقضی شده است")
            self.database.execute(
                "UPDATE control_intents SET status='CANCELLED' WHERE id=? AND status NOT IN ('EXECUTED','CANCELLED')",
                (intent_id,),
            )
        self.database.audit(user.username, "CONTROL_CANCEL", "control_intent", intent_id, {})
        return self.database.one("SELECT * FROM control_intents WHERE id=?", (intent_id,)) or {}

    def _check_preconditions(self, action: ControlAction) -> None:
        snapshot = self.state_snapshot()
        telemetry_event = snapshot.get("topics", {}).get("telemetry")
        if not telemetry_event:
            raise HTTPException(409, "تله‌متری زنده در دسترس نیست")
        age = int(time.time() * 1000) - telemetry_event["received_at_ms"]
        if age > 2000:
            raise HTTPException(409, "تله‌متری کهنه است؛ فرمان صادر نشد")
        telemetry = telemetry_event.get("payload", {})
        if action in {ControlAction.ARM, ControlAction.TAKEOFF}:
            if int(telemetry.get("gps_fix", 0)) < 3:
                raise HTTPException(409, "GPS سه‌بعدی معتبر نیست")
            if float(telemetry.get("battery_percent", 0)) < 25:
                raise HTTPException(409, "باتری برای آغاز پرواز کافی نیست")
            if not telemetry.get("ekf_healthy", False):
                raise HTTPException(409, "EKF سالم نیست")

    async def _send_gateway(self, intent: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.control_gateway_url or len(self.settings.control_gateway_secret) < 24:
            raise HTTPException(503, "تنظیمات درگاه کنترل واقعی کامل نیست")
        body = json.dumps(
            {"intent_id": intent["id"], "action": intent["action"], "issued_at_ms": int(time.time() * 1000)},
            separators=(",", ":"),
        ).encode()
        signature = hmac.new(self.settings.control_gateway_secret.encode(), body, hashlib.sha256).hexdigest()
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                response = await client.post(
                    self.settings.control_gateway_url,
                    content=body,
                    headers={"content-type": "application/json", "x-dashboard-signature": signature},
                )
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(502, "درگاه کنترل فرمان را تأیید نکرد") from exc
