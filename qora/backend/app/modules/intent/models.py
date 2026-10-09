"""Intent graph models — ERD §4 (INTENTS, CAPABILITIES, USER_INTENT_HISTORY)."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Intent(Base):
    __tablename__ = "intents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    parent_intent_id: Mapped[int | None] = mapped_column(ForeignKey("intents.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), default="primary")  # primary|secondary|composite


class Capability(Base):
    __tablename__ = "capabilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")


class IntentCapability(Base):
    __tablename__ = "intent_capability_map"

    intent_id: Mapped[int] = mapped_column(ForeignKey("intents.id"), primary_key=True)
    capability_id: Mapped[int] = mapped_column(ForeignKey("capabilities.id"), primary_key=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)


class UserIntentHistory(Base):
    __tablename__ = "user_intent_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    intent_id: Mapped[int] = mapped_column(ForeignKey("intents.id"))
    conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    entities: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
