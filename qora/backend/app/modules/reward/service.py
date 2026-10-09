"""Reward Engine — eligibility → anti-abuse → calculation → off-chain ledger [PRD]."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.reward.models import RewardAccount, RewardEvent, RewardLedgerEntry

UNIT_PER_SUCCESS = 10
UNIT_PER_PARTIAL = 3


class RewardService:
    @staticmethod
    def _account(db: Session, user_id: int) -> RewardAccount:
        acc = db.scalar(select(RewardAccount).where(RewardAccount.user_id == user_id))
        if not acc:
            acc = RewardAccount(user_id=user_id)
            db.add(acc)
            db.flush()
        return acc

    @staticmethod
    def process_outcome(db: Session, user_id: int, session_id: int, outcome_status: str, score: float):
        """Only real outcomes pay [PRD]. Idempotent per session."""
        key = f"session:{session_id}:user:{user_id}:outcome_reward"
        if db.scalar(select(RewardEvent).where(RewardEvent.idempotency_key == key)):
            return  # replay safety [TECH]
        units = 0
        if outcome_status == "SUCCESS":
            units = int(UNIT_PER_SUCCESS * (0.5 + score / 2))
        elif outcome_status == "PARTIAL":
            units = UNIT_PER_PARTIAL
        if units <= 0:
            return
        ev = RewardEvent(
            subject_type="session", subject_id=session_id,
            kind="outcome_reward", units=units,
            quality_multiplier=round(0.5 + score / 2, 3),
            status="SETTLED", idempotency_key=key,
        )
        db.add(ev)
        db.flush()
        acc = RewardService._account(db, user_id)
        acc.balance_units += units
        db.add(RewardLedgerEntry(
            account_id=acc.id, event_id=ev.id, direction="CREDIT", units=units,
            reason=f"Successful session #{session_id}", idempotency_key=key + ":credit",
        ))
        db.commit()

    @staticmethod
    def me(db: Session, user_id: int) -> dict:
        acc = RewardService._account(db, user_id)
        db.commit()
        events = db.scalars(select(RewardEvent).where(RewardEvent.subject_type == "session").order_by(RewardEvent.occurred_at.desc()).limit(20)).all()
        entries = db.scalars(select(RewardLedgerEntry).where(RewardLedgerEntry.account_id == acc.id).order_by(RewardLedgerEntry.created_at.desc()).limit(50)).all()
        return {
            "balance_units": acc.balance_units,
            "frozen_units": acc.frozen_units,
            "ledger": [{"id": e.id, "direction": e.direction, "units": e.units, "reason": e.reason, "created_at": e.created_at} for e in entries],
            "recent_events": [{"id": e.id, "kind": e.kind, "units": e.units, "status": e.status} for e in events],
        }
