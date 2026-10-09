"""Knowledge module — upload → scan → extract → normalize → chunk → embed → index [TECH].

Creator UX never says 'RAG' [PRD] — the surface is 'add my training material'.
ERD §5: KnowledgeCollection, KnowledgeSource, KnowledgeDocument, KnowledgeChunk, KnowledgeVersion.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeCollection(Base):
    __tablename__ = "knowledge_collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creator_profiles.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class KnowledgeSource(Base):
    """Freshness fields are part of Trust & Ranking [PRD]."""

    __tablename__ = "knowledge_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("knowledge_collections.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="upload")  # upload|url|api
    name: Mapped[str] = mapped_column(String(200))
    scan_status: Mapped[str] = mapped_column(String(12), default="pending")  # pending|clean|blocked
    source_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    freshness_policy: Mapped[str] = mapped_column(String(20), default="stale_after_90d")


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("knowledge_sources.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    mime: Mapped[str] = mapped_column(String(40), default="text/plain")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("knowledge_documents.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(JSON, default=list)
    chunk_meta: Mapped[dict] = mapped_column("metadata_json", JSON, default=dict)


class KnowledgeVersion(Base):
    """A Service Version binds to a Knowledge Version [ARCHITECTURE §4.13]."""

    __tablename__ = "knowledge_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("knowledge_collections.id"), index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)  # {source_ids, chunk_count, document_ids}
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
