"""Outcome models — ERD §6 OUTCOME_RECORDS.

[PRD] North Star = Successful Service Sessions. Outcome is NOT a like button [TECH].
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OutcomeRecord(Base):
    __tablename__ = "outcome_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("service_sessions.id"), unique=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("ai_services.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(10), default="UNKNOWN")  # SUCCESS|PARTIAL|FAILED|UNKNOWN
    score: Mapped[float] = mapped_column(Float, default=0.0)
    signals: Mapped[dict] = mapped_column(JSON, default=dict)  # service|completion|structured|confirmation|followup
    user_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    evaluator_notes: Mapped[str] = mapped_column(Text, default="")
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
