from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .auth import CurrentUser, create_token, decode_token, get_current_user, verify_password
from .chat import AdvisoryService
from .control import CRITICAL_ACTIONS, ControlService
from .database import Database
from .hub import TelemetryHub
from .ingest import IngestServers, SampleLimiter
from .models import (
    ChatRequest,
    ChatResponse,
    ControlDecisionRequest,
    ControlIntentRequest,
    LoginRequest,
    Role,
    TokenResponse,
    UserView,
)
from .settings import Settings, get_settings


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Runtime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db = Database(settings.database_path)
        self.hub = TelemetryHub(settings.ws_queue_size)
        self.samples = SampleLimiter(settings.telemetry_sample_hz)
        self.ingest = IngestServers(
            self.handle_envelope,
            self.invalid_envelope,
            settings.ingest_shared_secret or None,
        )
        self.chat = AdvisoryService(settings, self.db)
        self.control = ControlService(settings, self.db, self.hub.snapshot)
        self.ws_tickets: dict[str, tuple[str, int]] = {}

    async def start(self) -> None:
        self.db.initialize(self.settings)
        await self.ingest.start(
            self.settings.udp_host,
            self.settings.udp_port,
            self.settings.tcp_host,
            self.settings.tcp_port,
        )
        logger.info("ingest ready udp=%s tcp=%s", self.settings.udp_port, self.settings.tcp_port)

    async def stop(self) -> None:
        await self.ingest.stop()
        self.db.close()

    def invalid_envelope(self) -> None:
        self.hub.invalid += 1

    async def handle_envelope(self, envelope, transport: str) -> None:
        event = await self.hub.publish(envelope, transport)
        if envelope.topic == "alert":
            self.db.save_alert(envelope.payload, envelope.source, envelope.sent_at_ms)
        elif envelope.topic == "telemetry" and self.samples.allow(envelope.source):
            self.db.save_telemetry(envelope.source, envelope.payload, event["received_at_ms"])

    def issue_ws_ticket(self, username: str) -> str:
        now = int(time.time())
        self.ws_tickets = {key: value for key, value in self.ws_tickets.items() if value[1] >= now}
        ticket = secrets.token_urlsafe(32)
        self.ws_tickets[ticket] = (username, now + 30)
        return ticket

    def consume_ws_ticket(self, ticket: str) -> str | None:
        value = self.ws_tickets.pop(ticket, None)
        now = int(time.time())
        # Periodically clean up expired tickets on every consume call
        self.ws_tickets = {key: val for key, val in self.ws_tickets.items() if val[1] >= now}
        if not value or value[1] < now:
            return None
        return value[0]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    runtime = Runtime(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await runtime.start()
        yield
        await runtime.stop()

    app = FastAPI(
        title="Safe Autonomy Flight Dashboard API",
        version=__version__,
        description="Dashboard and supervised-control gateway; model output is advisory only.",
        lifespan=lifespan,
    )
    app.state.runtime = runtime
    app.dependency_overrides[get_settings] = lambda: settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["authorization", "content-type", "idempotency-key"],
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health/live")
    def health_live() -> dict[str, Any]:
        return {"status": "ok", "version": __version__}

    @app.get("/health/ready")
    def health_ready() -> dict[str, Any]:
        database_ok = False
        try:
            row = runtime.db.one("SELECT 1 AS ok")
            database_ok = bool(row and row["ok"] == 1)
        except Exception:
            database_ok = False
        return {
            "status": "ready" if database_ok else "not_ready",
            "database": database_ok,
            "udp_port": settings.udp_port,
            "tcp_port": settings.tcp_port,
            "control_mode": settings.control_mode,
        }

    # Simple in-memory login rate limiter: 5 failures / minute / IP+username.
    _login_failures: dict[str, list[float]] = {}

    # Simple in-memory login rate limiter: 10 failures/minute keyed by username.
    _login_failures: dict[str, list[float]] = {}

    @app.post("/api/v1/auth/login", response_model=TokenResponse)
    def login(request: LoginRequest) -> TokenResponse:
        now = time.time()
        key = request.username.lower()
        failures = [t for t in _login_failures.get(key, []) if now - t < 60.0]
        if len(failures) >= 10:
            raise HTTPException(429, "تعداد تلاش‌های ورود بیش از حد است؛ یک دقیقه بعد تلاش کنید")
        row = runtime.db.one("SELECT * FROM users WHERE username=? AND active=1", (request.username,))
        if not row or not verify_password(request.password, row["password_hash"]):
            failures.append(now)
            _login_failures[key] = failures
            raise HTTPException(401, "نام کاربری یا گذرواژه نادرست است")
        _login_failures.pop(key, None)
        role = Role(row["role"])
        runtime.db.audit(row["username"], "LOGIN", "session", "new", {})
        return TokenResponse(
            access_token=create_token(row["username"], role, settings),
            expires_in=settings.jwt_ttl_seconds,
            role=role,
            display_name=row["display_name"],
        )

    @app.get("/api/v1/session", response_model=UserView)
    def session(user: CurrentUser = Depends(get_current_user)) -> UserView:
        return UserView(username=user.username, display_name=user.display_name, role=user.role)

    @app.post("/api/v1/ws-ticket")
    def websocket_ticket(user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
        return {"ticket": runtime.issue_ws_ticket(user.username), "expires_in": 30}

    @app.get("/api/v1/dashboard/bootstrap")
    def bootstrap(user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
        alerts = runtime.db.all("SELECT * FROM alerts ORDER BY created_at_ms DESC LIMIT 50")
        intents = runtime.db.all("SELECT * FROM control_intents ORDER BY created_at_ms DESC LIMIT 30")
        return {
            "user": {"username": user.username, "display_name": user.display_name, "role": user.role},
            "live": runtime.hub.snapshot(),
            "alerts": alerts,
            "control_intents": intents,
            "capabilities": {
                "control_mode": settings.control_mode,
                "dual_approval": settings.control_require_dual_approval,
                "allowed_actions": [item.value for item in CRITICAL_ACTIONS] + ["HOLD", "RESUME_MISSION", "DISARM"],
                "model_control_authority": False,
            },
            "server_time_ms": int(time.time() * 1000),
        }

    @app.get("/api/v1/telemetry/history")
    def telemetry_history(
        limit: int = Query(default=300, ge=1, le=1200),
        user: CurrentUser = Depends(get_current_user),
    ) -> list[dict[str, Any]]:
        return runtime.hub.telemetry_history(limit)

    @app.get("/api/v1/alerts")
    def alerts(limit: int = Query(100, ge=1, le=500), user: CurrentUser = Depends(get_current_user)):
        return runtime.db.all("SELECT * FROM alerts ORDER BY created_at_ms DESC LIMIT ?", (limit,))

    @app.post("/api/v1/alerts/{alert_id}/ack")
    def acknowledge_alert(alert_id: str, user: CurrentUser = Depends(get_current_user)):
        row = runtime.db.one("SELECT * FROM alerts WHERE id=?", (alert_id,))
        if not row:
            raise HTTPException(404, "هشدار یافت نشد")
        runtime.db.execute(
            "UPDATE alerts SET acknowledged_at_ms=?,acknowledged_by=? WHERE id=? AND acknowledged_at_ms IS NULL",
            (int(time.time() * 1000), user.username, alert_id),
        )
        runtime.db.audit(user.username, "ALERT_ACK", "alert", alert_id, {})
        return runtime.db.one("SELECT * FROM alerts WHERE id=?", (alert_id,))

    @app.get("/api/v1/routes")
    def route_candidates(user: CurrentUser = Depends(get_current_user)):
        return runtime.hub.snapshot()["topics"].get("route_candidates", {"payload": {"routes": []}})

    @app.post("/api/v1/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest, user: CurrentUser = Depends(get_current_user)) -> ChatResponse:
        # If client supplied a conversation_id, make sure it is not already
        # owned by a different user to prevent cross-user state pollution.
        if request.conversation_id:
            existing = runtime.db.one(
                "SELECT username FROM chat_messages WHERE conversation_id=? LIMIT 1",
                (request.conversation_id,),
            )
            if existing and existing["username"] != user.username:
                raise HTTPException(403, "شناسه گفت‌وگو متعلق به کاربر دیگری است")
        return await runtime.chat.ask(user.username, request.conversation_id, request.message, runtime.hub.snapshot())

    @app.get("/api/v1/chat/{conversation_id}")
    def chat_history(conversation_id: str, user: CurrentUser = Depends(get_current_user)):
        return runtime.db.all(
            "SELECT id,conversation_id,role,content,metadata_json,created_at_ms FROM chat_messages WHERE conversation_id=? AND username=? ORDER BY created_at_ms",
            (conversation_id, user.username),
        )

    @app.get("/api/v1/control/intents")
    def control_intents(user: CurrentUser = Depends(get_current_user)):
        return runtime.db.all("SELECT * FROM control_intents ORDER BY created_at_ms DESC LIMIT 100")

    @app.post("/api/v1/control/intents")
    async def create_control_intent(request: ControlIntentRequest, user: CurrentUser = Depends(get_current_user)):
        intent = runtime.control.create_intent(request, user)
        if intent.get("status") == "APPROVED":
            return await runtime.control.execute(intent["id"])
        return intent

    @app.post("/api/v1/control/intents/{intent_id}/approve")
    async def approve_control_intent(
        intent_id: str,
        request: ControlDecisionRequest,
        user: CurrentUser = Depends(get_current_user),
    ):
        return await runtime.control.approve(intent_id, request.note, user)

    @app.post("/api/v1/control/intents/{intent_id}/cancel")
    def cancel_control_intent(
        intent_id: str,
        request: ControlDecisionRequest,
        user: CurrentUser = Depends(get_current_user),
    ):
        return runtime.control.cancel(intent_id, user)

    @app.websocket("/ws/live")
    async def websocket_live(websocket: WebSocket, ticket: str):
        username = runtime.consume_ws_ticket(ticket)
        if not username:
            await websocket.close(code=4401)
            return
        await websocket.accept()
        subscription_id, subscriber = await runtime.hub.subscribe()
        await websocket.send_json({"type": "snapshot", "data": runtime.hub.snapshot(), "username": username})
        try:
            while True:
                try:
                    event = await asyncio.wait_for(subscriber.queue.get(), timeout=10)
                    event["client_queue_drops"] = subscriber.dropped
                    await websocket.send_json(event)
                except TimeoutError:
                    await websocket.send_json({"type": "heartbeat", "server_time_ms": int(time.time() * 1000)})
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            await runtime.hub.unsubscribe(subscription_id)

    return app


app = create_app()
