"""Runtime models — ERD §6 (SERVICE_SESSIONS, SESSION_EVENTS, MODEL_CALLS, TOOL_INVOCATIONS, FAILURE_EVENTS)."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ServiceSession(Base):
    __tablename__ = "service_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("ai_services.id"), index=True)
    service_version_id: Mapped[int] = mapped_column(ForeignKey("service_versions.id"))
    conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="started")  # started|running|awaiting_permission|completed|failed|abandoned
    context_shared: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SessionEvent(Base):
    __tablename__ = "session_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("service_sessions.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # permission_check|model_call|tool_call|guardrail|recovery|...
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ModelCall(Base):
    __tablename__ = "model_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("service_sessions.id"), index=True)
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(60))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(10), default="ok")


class ToolInvocation(Base):
    __tablename__ = "tool_invocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("service_sessions.id"), index=True)
    tool_name: Mapped[str] = mapped_column(String(80))
    input: Mapped[dict] = mapped_column(JSON, default=dict)
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(10), default="ok")  # ok|denied|error|timeout
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)


class FailureEvent(Base):
    """Failure taxonomy + recovery action (ARCHITECTURE §4.28) [TECH]."""

    __tablename__ = "failure_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("service_sessions.id"), index=True)
    failure_type: Mapped[str] = mapped_column(String(30))
    recovery_action: Mapped[str] = mapped_column(String(20))  # retry|fallback_model|fallback_service|direct_qora|ask_user|stop
    detail: Mapped[str] = mapped_column(Text, default="")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
