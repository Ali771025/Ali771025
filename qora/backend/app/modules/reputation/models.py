"""Reputation models — ERD §8 (TRUST_SCORES, REPUTATION_EVENTS).

[PRD] Creator trust and Service trust stay separate. Event-driven, component scores kept.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TrustScore(Base):
    __tablename__ = "trust_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(10))  # creator|service
    subject_id: Mapped[int] = mapped_column(Integer, index=True)
    overall: Mapped[float] = mapped_column(Float, default=0.5)
    components: Mapped[dict] = mapped_column(JSON, default=dict)  # safety, reliability, quality, freshness
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ReputationEvent(Base):
    __tablename__ = "reputation_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(10))
    subject_id: Mapped[int] = mapped_column(Integer, index=True)
    kind: Mapped[str] = mapped_column(String(40))  # successful_outcome|confirmed_complaint|repeat_use|...
    delta: Mapped[float] = mapped_column(Float, default=0.0)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
