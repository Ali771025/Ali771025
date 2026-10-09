"""Creator interview models — the no-code creation flow [PRD: Conversation over Configuration]."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CreatorInterview(Base):
    """Intent → Interview → Generate → Simulate → Review → Visibility → Qualify [PRD flow]."""

    __tablename__ = "creator_interviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creator_profiles.id"), index=True)
    intent_statement: Mapped[str] = mapped_column(Text)  # "What should people be able to do?"
    status: Mapped[str] = mapped_column(String(20), default="interviewing")
    # interviewing | spec_ready | simulated | qualified | published | abandoned
    gaps_detected: Mapped[list] = mapped_column(JSON, default=list)
    answers: Mapped[dict] = mapped_column(JSON, default=dict)  # {question_id: answer_text}
    spec_draft: Mapped[dict] = mapped_column(JSON, default=dict)
    service_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # created on publish
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
