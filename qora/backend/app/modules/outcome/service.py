"""Outcome Engine v2 — composite, structured signals [PRD Phase 3]."""
import hashlib
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.outcome.models import OutcomeRecord
from app.shared.errors import CONFLICT, NOT_FOUND, AppError

SIGNAL_WEIGHTS = {
    "service": 0.20,
    "completion": 0.30,
    "structured": 0.20,
    "confirmation": 0.20,
    "followup": 0.10,
}


def composite_score(signals: dict) -> float:
    """Score known signals; unknown confirmation/follow-up remain neutral, not failures."""
    total = 0.0
    for name, weight in SIGNAL_WEIGHTS.items():
        value = signals.get(name)
        if value is None:
            continue
        if isinstance(value, dict):
            if name == "confirmation":
                value = 0.6 * float(value.get("useful", 0.0)) + 0.4 * float(value.get("achieved_goal", 0.0))
            elif name == "followup":
                value = float(value.get("returned", 0.0))
            else:
                continue
        total += weight * max(0.0, min(1.0, float(value)))
    return round(total, 3)


def status_for_score(score: float) -> str:
    return "SUCCESS" if score >= 0.78 else "PARTIAL" if score >= 0.4 else "FAILED"


def _safe_feedback(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", " ", text)
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"\+?\d[\d\s().-]{7,}\d", " ", text)
    # Creator-facing reports use outcome language only, never internal implementation vocabulary.
    text = re.sub(r"\b(rag|embeddings?|prompts?)\b", " ", text, flags=re.IGNORECASE)
    return " ".join(text.split())[:240]


class OutcomeService:
    @staticmethod
    def evaluate(db: Session, session, version, run_result: dict) -> OutcomeRecord:
        """Evaluate service, completion, structured delivery, confirmation, and follow-up."""
        if not run_result.get("ok"):
            signals = {
                "service": 0.0,
                "completion": 0.0,
                "structured": 0.0,
                "confirmation": None,
                "followup": None,
                "satisfied_definition_signals": [],
            }
            rec = OutcomeRecord(
                session_id=session.id,
                service_id=session.service_id,
                user_id=session.user_id,
                status="FAILED",
                score=composite_score(signals),
                signals=signals,
                evaluator_notes=(run_result.get("failure") or {}).get("failure_type", "failed"),
            )
            db.add(rec)
            db.commit()
            db.refresh(rec)
            return rec

        outcome_def = version.outcome_definition or {}
        required = outcome_def.get("signals", ["deliverable_generated", "relevant_interaction"])
        service_signal = 1.0 if run_result.get("content") else 0.0
        satisfied = []
        for signal in required:
            if signal in ("deliverable_generated", "plan_produced") and run_result.get("deliverable"):
                satisfied.append(signal)
            elif signal == "relevant_interaction" and len(run_result.get("content") or "") > 40:
                satisfied.append(signal)
        completion = len(satisfied) / max(len(required), 1)
        structured = 1.0 if isinstance(run_result.get("deliverable"), (dict, list)) else 0.5
        signals = {
            "service": service_signal,
            "completion": round(completion, 3),
            "structured": structured,
            "confirmation": None,
            "followup": None,
            "satisfied_definition_signals": satisfied,
            "known_signal_weight": round(sum(SIGNAL_WEIGHTS[k] for k in ("service", "completion", "structured")), 3),
        }
        score = composite_score(signals)
        rec = OutcomeRecord(
            session_id=session.id,
            service_id=session.service_id,
            user_id=session.user_id,
            status=status_for_score(score),
            score=score,
            signals=signals,
            evaluator_notes=outcome_def.get("text", ""),
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return rec

    @staticmethod
    def confirm(db: Session, user_id: int, session_id: int, data: dict) -> OutcomeRecord:
        rec = db.scalar(select(OutcomeRecord).where(OutcomeRecord.session_id == session_id))
        if not rec:
            raise AppError(NOT_FOUND, "Outcome not found", 404)
        if rec.user_id != user_id:
            raise AppError(CONFLICT, "Not your session", 403)

        useful = bool(data.get("useful"))
        achieved = bool(data.get("achieved_goal"))
        from app.modules.runtime.service import RuntimeService

        sessions = RuntimeService.sessions_for_service(db, rec.service_id)
        repeated = sum(
            1 for row in sessions
            if row["user_id"] == user_id and row.get("status") == "completed"
        ) >= 2
        signals = dict(rec.signals or {})
        signals["confirmation"] = {
            "useful": float(useful),
            "achieved_goal": float(achieved),
            "notes": _safe_feedback(data.get("notes", "")),
        }
        raw_user_signals = data.get("signals") if isinstance(data.get("signals"), dict) else {}
        user_signals = {
            str(key)[:60]: float(value)
            for key, value in list(raw_user_signals.items())[:20]
            if isinstance(value, bool)
        }
        if user_signals:
            signals["user_signals"] = user_signals
            structured_check = sum(user_signals.values()) / len(user_signals)
            signals["structured"] = round(0.7 * float(signals.get("structured", 0.5)) + 0.3 * structured_check, 3)
        signals["followup"] = {"returned": 1.0} if repeated else None
        rec.signals = signals
        rec.user_confirmed = useful
        rec.score = composite_score(signals)
        rec.status = status_for_score(rec.score)
        db.commit()
        db.refresh(rec)

        note = _safe_feedback(data.get("notes", ""))
        RuntimeService.record_event(db, session_id, "outcome_confirmation", {
            "useful": useful,
            "achieved_goal": achieved,
            "followup_returned": repeated,
        })
        if (not useful or not achieved) and len(note) >= 8:
            from app.core.config import settings

            person_key = hashlib.sha256(f"{settings.SECRET_KEY}:{user_id}".encode()).hexdigest()[:16]
            RuntimeService.record_event(db, session_id, "unmet_request", {
                "note": note,
                "person_key": person_key,
                "source": "explicit_outcome_feedback",
                "active": True,
            })
        else:
            RuntimeService.clear_event(db, session_id, "unmet_request")
        db.commit()

        # User feedback is a trust signal, not a vanity like.
        from app.modules.reputation.service import ReputationService
        from app.modules.service.service import ServiceRegistry

        service = ServiceRegistry.get(db, rec.service_id)
        for subject_type, subject_id in (("service", rec.service_id), ("creator", service.creator_id)):
            if not useful or not achieved:
                ReputationService.apply_event(
                    db,
                    subject_type,
                    subject_id,
                    "confirmed_complaint",
                    idempotency_key=f"confirmation:{session_id}:{subject_type}:{subject_id}",
                    meta={"useful": useful, "achieved_goal": achieved},
                )
            else:
                ReputationService.apply_event(
                    db,
                    subject_type,
                    subject_id,
                    "quality_update",
                    idempotency_key=f"confirmation:{session_id}:{subject_type}:{subject_id}",
                    meta={"score": rec.score, "useful": True, "achieved_goal": True},
                )
        return rec

    @staticmethod
    def get_service_outcome_stats(db: Session) -> dict:
        """Interface used by discovery ranking (service module)."""
        out: dict[int, dict] = {}
        for rec in db.scalars(select(OutcomeRecord)).all():
            stat = out.setdefault(rec.service_id, {"sessions": 0, "score_sum": 0.0, "confirmed": 0, "successes": 0})
            stat["sessions"] += 1
            stat["score_sum"] += rec.score
            stat["successes"] += int(rec.status == "SUCCESS")
            stat["confirmed"] += int(rec.user_confirmed)
        for stat in out.values():
            stat["success_rate"] = round(stat["score_sum"] / max(stat["sessions"], 1), 3)
            stat["confirmed_rate"] = round(stat["confirmed"] / max(stat["sessions"], 1), 3)
            stat["completed_rate"] = round(stat["successes"] / max(stat["sessions"], 1), 3)
        return out

    @staticmethod
    def list_for_service(db: Session, service_id: int) -> list[dict]:
        """Interface for analytics (boundary rule: no cross-module model imports)."""
        rows = db.scalars(select(OutcomeRecord).where(OutcomeRecord.service_id == service_id)).all()
        return [
            {
                "session_id": row.session_id,
                "status": row.status,
                "score": row.score,
                "user_confirmed": row.user_confirmed,
                "user_id": row.user_id,
                "evaluated_at": row.evaluated_at,
            }
            for row in rows
        ]

    @staticmethod
    def session_outcome(db: Session, session_id: int) -> OutcomeRecord | None:
        return db.scalar(select(OutcomeRecord).where(OutcomeRecord.session_id == session_id))
