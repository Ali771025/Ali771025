"""Daily creator metrics and durable insight inbox [PRD Phase 4]."""
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CreatorMetric(Base):
    __tablename__ = "creator_metrics"
    __table_args__ = (UniqueConstraint("service_id", "bucket_date", name="uq_creator_metric_service_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("ai_services.id"), index=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creator_profiles.id"), index=True)
    bucket_date: Mapped[date] = mapped_column(Date, index=True)
    users_count: Mapped[int] = mapped_column(Integer, default=0)
    sessions_count: Mapped[int] = mapped_column(Integer, default=0)
    successful_sessions: Mapped[int] = mapped_column(Integer, default=0)
    returned_users: Mapped[int] = mapped_column(Integer, default=0)
    useful_votes: Mapped[int] = mapped_column(Integer, default=0)
    unmet_request_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    def as_dict(self) -> dict:
        return {
            "service_id": self.service_id,
            "creator_id": self.creator_id,
            "bucket_date": self.bucket_date.isoformat(),
            "users_count": self.users_count,
            "sessions_count": self.sessions_count,
            "successful_sessions": self.successful_sessions,
            "returned_users": self.returned_users,
            "useful_votes": self.useful_votes,
            "unmet_request_count": self.unmet_request_count,
        }


class InsightReport(Base):
    __tablename__ = "insight_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("ai_services.id"), index=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creator_profiles.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)  # demand_cluster|knowledge_gap|improvement
    signature: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    summary: Mapped[str] = mapped_column(Text)
    suggested_update: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="new")  # new|acted_on|dismissed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "service_id": self.service_id,
            "kind": self.kind,
            "summary": self.summary,
            "suggested_update": self.suggested_update,
            "evidence": self.evidence or {},
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
