"""Reputation service — event-driven deltas (Phase 3 brings full rules)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.reputation.models import ReputationEvent, TrustScore

DELTAS = {"SUCCESS": 0.01, "PARTIAL": 0.0, "FAILED": -0.015, "UNKNOWN": 0.0}


class ReputationService:
    @staticmethod
    def apply_outcome_event(db: Session, creator_id: int, service_id: int, outcome_status: str):
        delta = DELTAS.get(outcome_status, 0.0)
        for subject_type, subject_id in (("creator", creator_id), ("service", service_id)):
            score = db.scalar(select(TrustScore).where(TrustScore.subject_type == subject_type, TrustScore.subject_id == subject_id))
            if not score:
                score = TrustScore(subject_type=subject_type, subject_id=subject_id, overall=0.5, components={"reliability": 0.5, "quality": 0.5})
                db.add(score)
            score.overall = max(0.0, min(1.0, round(score.overall + delta, 4)))
            db.add(ReputationEvent(
                subject_type=subject_type, subject_id=subject_id,
                kind="successful_outcome" if delta >= 0 else "quality_update",
                delta=delta, meta={"outcome_status": outcome_status},
            ))
            if subject_type == "creator":
                from app.modules.profile.service import ProfileService

                creator = ProfileService.get_creator_by_id(db, subject_id)
                if creator:
                    creator.trust_score = score.overall
        db.commit()

    @staticmethod
    def trust_for(db: Session, subject_type: str, subject_id: int) -> dict:
        score = db.scalar(select(TrustScore).where(TrustScore.subject_type == subject_type, TrustScore.subject_id == subject_id))
        return {
            "overall": score.overall if score else 0.5,
            "components": score.components if score else {},
        }
