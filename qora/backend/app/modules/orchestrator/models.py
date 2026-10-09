"""Orchestration models — multi-service chains in one conversation [PRD Phase 3]."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.db import Base


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class OrchestrationPlan(Base):
    __tablename__ = "orchestration_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    goal_text: Mapped[str] = mapped_column(Text)
    intent_slug: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(24), default="draft")  # draft|running|completed|partial|failed
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "goal_text": self.goal_text,
            "intent_slug": self.intent_slug,
            "status": self.status,
            "summary": self.summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class OrchestrationStep(Base):
    __tablename__ = "orchestration_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("orchestration_plans.id"), index=True)
    step_order: Mapped[int] = mapped_column(Integer, default=0)
    service_id: Mapped[int] = mapped_column(Integer)
    service_name: Mapped[str] = mapped_column(String(128), default="")
    role: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(24), default="pending")  # pending|done|failed|skipped
    score: Mapped[float] = mapped_column(Float, default=0.0)
    session_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output: Mapped[dict] = mapped_column(JSON, default=dict)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "order": self.step_order,
            "service_id": self.service_id,
            "service_name": self.service_name,
            "role": self.role,
            "status": self.status,
            "score": self.score,
            "session_id": self.session_id,
            "output": self.output or {},
        }
