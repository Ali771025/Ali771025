"""Audit log for sensitive platform operations [PRD Phase 4: compliance & audit].

One policy model: every sensitive action records actor, action, target, detail.
"""
import json
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    target: Mapped[str] = mapped_column(String(128), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "actor_id": self.actor_id,
            "action": self.action,
            "target": self.target,
            "detail": self.detail,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def record(db, actor_id: int | None, action: str, target: str = "", detail=None) -> AuditLog:
    """Record a sensitive operation in the caller's transaction."""
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        target=str(target)[:128],
        detail=detail if isinstance(detail, str) else json.dumps(detail or {}, default=str),
    )
    db.add(entry)
    db.flush()
    return entry


def list_entries(db, limit: int = 50, action: str | None = None) -> list[dict]:
    q = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if action:
        q = q.where(AuditLog.action == action)
    return [e.as_dict() for e in db.scalars(q).all()]
