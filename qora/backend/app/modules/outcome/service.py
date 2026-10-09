"""Outcome Engine v1 — evaluate sessions against the service's outcome_definition [PRD]."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.outcome.models import OutcomeRecord
from app.shared.errors import CONFLICT, NOT_FOUND, AppError


class OutcomeService:
    @staticmethod
    def evaluate(db: Session, session, version, run_result: dict) -> OutcomeRecord:
        """Composite signals [TECH]: service + completion + structured + confirmation(follow-up)."""
        if not run_result.get("ok"):
            rec = OutcomeRecord(
                session_id=session.id,
                service_id=session.service_id,
                user_id=session.user_id,
                status="FAILED",
                score=0.0,
                signals={"service": 0.0, "completion": 0.0},
                evaluator_notes=(run_result.get("failure") or {}).get("failure_type", "failed"),
            )
            db.add(rec)
            db.commit()
            db.refresh(rec)
            return rec

        outcome_def = version.outcome_definition or {}
        required = outcome_def.get("signals", ["deliverable_generated", "relevant_interaction"])

        # service signals: the runtime produced content + a deliverable
        svc_sig = 1.0 if run_result.get("content") else 0.0
        # completion signals: required definition signals satisfied by the run
        completion = 0.0
        satisfied = []
        for sig in required:
            if sig == "deliverable_generated" and run_result.get("deliverable"):
                completion += 1
                satisfied.append(sig)
            elif sig == "relevant_interaction" and len((run_result.get("content") or "")) > 40:
                completion += 1
                satisfied.append(sig)
            elif sig == "plan_produced" and run_result.get("deliverable"):
                completion += 1
                satisfied.append(sig)
        completion = completion / max(len(required), 1)
        structured = 1.0 if run_result.get("deliverable") else 0.5
        score = round(0.35 * svc_sig + 0.45 * completion + 0.20 * structured, 3)
        status = "SUCCESS" if score >= 0.75 else "PARTIAL" if score >= 0.4 else "FAILED"

        rec = OutcomeRecord(
            session_id=session.id,
            service_id=session.service_id,
            user_id=session.user_id,
            status=status,
            score=score,
            signals={
                "service": svc_sig,
                "completion": completion,
                "structured": structured,
                "confirmation": None,  # filled by user confirm [TECH: not just a like]
                "satisfied_definition_signals": satisfied,
            },
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
        useful = 1.0 if data.get("useful") else 0.0
        achieved = 1.0 if data.get("achieved_goal") else 0.0
        rec.user_confirmed = bool(data.get("useful"))
        rec.signals = {
            **(rec.signals or {}),
            "confirmation": {"useful": useful, "achieved_goal": achieved, "notes": data.get("notes", "")},
            "followup": {"returned": True},
        }
        rec.score = round(0.7 * rec.score + 0.3 * (0.6 * useful + 0.4 * achieved), 3)
        if rec.status == "PARTIAL" and rec.score >= 0.75:
            rec.status = "SUCCESS"
        db.commit()
        db.refresh(rec)
        return rec

    @staticmethod
    def get_service_outcome_stats(db: Session) -> dict:
        """Interface used by discovery ranking (service module)."""
        out: dict[int, dict] = {}
        for rec in db.scalars(select(OutcomeRecord)).all():
            st = out.setdefault(rec.service_id, {"sessions": 0, "score_sum": 0.0, "confirmed": 0})
            st["sessions"] += 1
            st["score_sum"] += rec.score
            if rec.user_confirmed:
                st["confirmed"] += 1
        for sid, st in out.items():
            st["success_rate"] = round(st["score_sum"] / max(st["sessions"], 1), 3)
            st["confirmed_rate"] = round(st["confirmed"] / max(st["sessions"], 1), 3)
        return out

    @staticmethod
    def session_outcome(db: Session, session_id: int) -> OutcomeRecord | None:
        return db.scalar(select(OutcomeRecord).where(OutcomeRecord.session_id == session_id))
