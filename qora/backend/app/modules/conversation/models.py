"""Conversation domain — ERD §3 (CONVERSATIONS, MESSAGES, INVOCATION_TRACES)."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    active_intent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_service_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_journey_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    recovery_state: Mapped[str] = mapped_column(String(30), default="normal")  # normal|service_failed|awaiting_permission
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user|assistant|service|system
    content: Mapped[str] = mapped_column(Text, default="")
    content_blocks: Mapped[dict] = mapped_column(JSON, default=dict)  # rich cards, suggestions
    status: Mapped[str] = mapped_column(String(20), default="sent")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class InvocationTrace(Base):
    """Full trace per request [TECH] — debugging, reputation, evaluation, reward."""

    __tablename__ = "invocation_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    message_id: Mapped[int] = mapped_column(Integer)  # triggering user message
    intent_slug: Mapped[str] = mapped_column(String(80), default="")
    intent_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    entities: Mapped[dict] = mapped_column(JSON, default=dict)
    candidate_services: Mapped[list] = mapped_column(JSON, default=list)
    chosen_service_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chosen_service_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context_shared: Mapped[dict] = mapped_column(JSON, default=dict)
    permission_needed: Mapped[list] = mapped_column(JSON, default=list)
    session_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome_status: Mapped[str] = mapped_column(String(10), default="UNKNOWN")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
