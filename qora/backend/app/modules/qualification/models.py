"""Qualification & Simulation models — ERD §7.

[PRD criteria] utility · quality · differentiation · safety · completeness · reliability.
Results: READY_TO_PUBLISH | NEEDS_IMPROVEMENT | RESTRICTED.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

SIM_KINDS = ["normal", "ambiguous", "edge", "boundary", "unsafe", "unsupported", "adversarial"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SimulationCase(Base):
    __tablename__ = "simulation_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[int] = mapped_column(Integer, index=True)
    kind: Mapped[str] = mapped_column(String(20))  # SIM_KINDS
    input: Mapped[str] = mapped_column(Text)
    expected_behavior: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    interview_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    service_id: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(12), default="pending")  # pending|running|done
    summary: Mapped[dict] = mapped_column(JSON, default=dict)  # {avg_score, per_kind}
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SimulationResult(Base):
    """TestCase · ExpectedBehavior · ActualBehavior · Evaluation · Score · FailureReason."""

    __tablename__ = "simulation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("simulation_runs.id"), index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("simulation_cases.id"))
    kind: Mapped[str] = mapped_column(String(20))
    actual_behavior: Mapped[str] = mapped_column(Text, default="")
    evaluation: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    failure_reason: Mapped[str] = mapped_column(Text, default="")


class QualificationRun(Base):
    __tablename__ = "qualification_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[int] = mapped_column(Integer, index=True)
    service_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interview_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result: Mapped[str] = mapped_column(String(30), default="NEEDS_IMPROVEMENT")
    scores: Mapped[dict] = mapped_column(JSON, default=dict)  # per criterion
    checks: Mapped[list] = mapped_column(JSON, default=list)  # [{criterion, passed, detail}]
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DuplicateCheck(Base):
    __tablename__ = "duplicate_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    qualification_run_id: Mapped[int] = mapped_column(ForeignKey("qualification_runs.id"), index=True)
    similar_service_id: Mapped[int] = mapped_column(Integer)
    similar_service_name: Mapped[str] = mapped_column(String(160), default="")
    similarity: Mapped[float] = mapped_column(Float, default=0.0)
    resolution: Mapped[str] = mapped_column(String(30), default="unique")  # unique|needs_differentiation|merge_suggested
    question: Mapped[str] = mapped_column(Text, default="")
