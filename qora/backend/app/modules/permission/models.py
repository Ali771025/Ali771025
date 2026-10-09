"""Permission models — ERD §2 CONTEXT_GRANTS.

[PRD hard rule] personal context is never passed to a service without a grant.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ContextGrant(Base):
    __tablename__ = "context_grants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("ai_services.id"), index=True)
    context_type: Mapped[str] = mapped_column(String(40))  # career|goals|preferences|travel|language
    scope: Mapped[str] = mapped_column(Text, default="*")  # comma-separated fields or *
    mode: Mapped[str] = mapped_column(String(20))  # ALLOW_ONCE|ALWAYS_ALLOW|DENY
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # for ALLOW_ONCE
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
