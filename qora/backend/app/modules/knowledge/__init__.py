"""Knowledge module — Phase 2 delivers the ingestion pipeline (ARCHITECTURE §4.13).

Phase 0/1 state: skeleton + a tiny model so service versions can reference collections.
The creator UX never says 'RAG' [PRD] — it's 'add my training material'.
"""
from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeCollection(Base):
    __tablename__ = "knowledge_collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creator_profiles.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


@router.get("/_status")
def status():
    return {
        "module": "knowledge",
        "phase": "skeleton",
        "planned": "upload → scan → extract → chunk → embed → index (Phase 2)",
        "freshness_fields": ["source_date", "ingested_at", "last_verified_at", "expires_at", "freshness_policy"],
    }
