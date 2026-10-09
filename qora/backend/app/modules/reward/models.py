"""Reward models — ERD §9 (REWARD_ACCOUNTS, REWARD_EVENTS, REWARD_LEDGER_ENTRIES).

[PRD] MVP is an off-chain ledger. Rewards follow useful outcomes — never messages/views/likes.
"""
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RewardAccount(Base):
    __tablename__ = "reward_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    balance_units: Mapped[int] = mapped_column(BigInteger, default=0)
    frozen_units: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(10), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RewardEvent(Base):
    __tablename__ = "reward_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(20))  # session|outcome|creator|campaign
    subject_id: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(30))  # outcome_reward|quality_bonus|correction|anti_abuse_reversal
    units: Mapped[int] = mapped_column(BigInteger, default=0)
    quality_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[str] = mapped_column(String(12), default="PENDING")  # PENDING|ELIGIBLE|SETTLED|REVERSED
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RewardLedgerEntry(Base):
    """Append-only double-entry rows — corrections are compensating entries [TECH]."""

    __tablename__ = "reward_ledger_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("reward_accounts.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("reward_events.id"))
    direction: Mapped[str] = mapped_column(String(6))  # CREDIT|DEBIT
    units: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(String(255), default="")
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
