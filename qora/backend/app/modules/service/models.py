"""Service registry models — ERD §5 (SERVICES, SERVICE_VERSIONS, LIFECYCLE)."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# [PRD] visibility set; lifecycle internals are [TECH]
LIFECYCLE = [
    "draft", "ready_for_test", "testing", "private", "unlisted",
    "qualification_pending", "ready", "improve", "restricted",
    "published", "updated", "requalification",
]

ALLOWED_TRANSITIONS = {
    "draft": ["ready_for_test", "private"],
    "ready_for_test": ["testing", "draft"],
    "testing": ["private", "qualification_pending", "draft"],
    "private": ["unlisted", "qualification_pending"],
    "unlisted": ["qualification_pending", "private"],
    "qualification_pending": ["ready", "improve", "restricted"],
    "improve": ["qualification_pending", "draft"],
    "ready": ["published"],
    "published": ["updated", "unlisted", "restricted"],
    "updated": ["requalification", "published"],
    "requalification": ["ready", "improve", "restricted"],
    "restricted": ["draft", "improve"],
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AiService(Base):
    __tablename__ = "ai_services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creator_profiles.id"), index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    summary: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    purpose: Mapped[str] = mapped_column(Text, default="")
    audience: Mapped[str] = mapped_column(String(255), default="")
    category: Mapped[str] = mapped_column(String(60), default="general")
    risk_level: Mapped[str] = mapped_column(String(20), default="LOW")  # LOW|MEDIUM|HIGH|RESTRICTED
    visibility: Mapped[str] = mapped_column(String(20), default="private")  # private|unlisted|public
    lifecycle_status: Mapped[str] = mapped_column(String(30), default="draft")
    current_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(20), default="none")
    intent_embedding: Mapped[list] = mapped_column(JSON, default=list)  # placeholder until pgvector
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ServiceVersion(Base):
    __tablename__ = "service_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("ai_services.id"), index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    purpose: Mapped[str] = mapped_column(Text, default="")
    method: Mapped[str] = mapped_column(Text, default="")
    behavior: Mapped[str] = mapped_column(Text, default="")
    system_instructions: Mapped[str] = mapped_column(Text, default="")
    boundaries: Mapped[str] = mapped_column(Text, default="")
    knowledge_config: Mapped[dict] = mapped_column(JSON, default=dict)
    tools_config: Mapped[dict] = mapped_column(JSON, default=dict)
    outcome_definition: Mapped[dict] = mapped_column(JSON, default=dict)  # [PRD] per-service outcome
    examples: Mapped[list] = mapped_column(JSON, default=list)
    evaluation_config: Mapped[dict] = mapped_column(JSON, default=dict)
    model_requirements: Mapped[dict] = mapped_column(JSON, default=dict)  # capability needs [PRD concept]
    context_requirements: Mapped[list] = mapped_column(JSON, default=list)  # context types needed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LifecycleTransition(Base):
    __tablename__ = "lifecycle_transitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("ai_services.id"), index=True)
    from_status: Mapped[str] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ServiceIntentMap(Base):
    __tablename__ = "service_intent_map"

    service_id: Mapped[int] = mapped_column(ForeignKey("ai_services.id"), primary_key=True)
    intent_id: Mapped[int] = mapped_column(ForeignKey("intents.id"), primary_key=True)
    relevance: Mapped[float] = mapped_column(Float, default=0.8)


class ServiceCapabilityMap(Base):
    __tablename__ = "service_capability_map"

    service_id: Mapped[int] = mapped_column(ForeignKey("ai_services.id"), primary_key=True)
    capability_id: Mapped[int] = mapped_column(ForeignKey("capabilities.id"), primary_key=True)
    level: Mapped[str] = mapped_column(String(20), default="strong")  # basic|strong|native


class FollowedService(Base):
    """Follow = 'add this intelligence to my toolkit' [PRD] — boosts personal fit."""

    __tablename__ = "followed_services"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("ai_services.id"), primary_key=True)
    followed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RankingConfiguration(Base):
    """Runtime-editable ranking weights [TECH]; one row per configuration key."""

    __tablename__ = "ranking_configurations"

    key: Mapped[str] = mapped_column(String(40), primary_key=True, default="default")
    weights: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
