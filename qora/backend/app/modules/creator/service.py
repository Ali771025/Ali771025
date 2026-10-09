"""Creator Platform service — interview lifecycle + publish pipeline."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.creator.interview import detect_gaps, generate_spec, next_question
from app.modules.creator.models import CreatorInterview
from app.shared.errors import CONFLICT, FORBIDDEN, NOT_FOUND, AppError


class CreatorService:
    @staticmethod
    def start(db: Session, creator_id: int, intent_statement: str) -> CreatorInterview:
        iv = CreatorInterview(
            creator_id=creator_id,
            intent_statement=intent_statement.strip(),
            gaps_detected=detect_gaps(intent_statement),
            answers={},
        )
        db.add(iv)
        db.commit()
        db.refresh(iv)
        return iv

    @staticmethod
    def get(db: Session, creator_id: int, interview_id: int) -> CreatorInterview:
        iv = db.get(CreatorInterview, interview_id)
        if not iv:
            raise AppError(NOT_FOUND, "Interview not found", 404)
        if iv.creator_id != creator_id:
            raise AppError(FORBIDDEN, "Not your interview", 403)
        return iv

    @staticmethod
    def list_for(db: Session, creator_id: int) -> list[CreatorInterview]:
        return list(db.scalars(select(CreatorInterview).where(CreatorInterview.creator_id == creator_id).order_by(CreatorInterview.created_at.desc())).all())

    @staticmethod
    def answer(db: Session, creator_id: int, interview_id: int, answers: list[dict]) -> dict:
        iv = CreatorService.get(db, creator_id, interview_id)
        store = dict(iv.answers or {})
        for a in answers:
            store[a["question_id"]] = a.get("text", "")
        iv.answers = store
        iv.updated_at = datetime.now(timezone.utc)

        nxt = next_question(iv.gaps_detected or [], store)
        if nxt is None:
            # interview complete → auto-draft the specification
            iv.spec_draft = generate_spec(iv.intent_statement, store)
            iv.status = "spec_ready"
            db.commit()
            return {"next_question": None, "interview_complete": True, "spec_draft": iv.spec_draft}
        db.commit()
        return {"next_question": nxt, "interview_complete": False, "gaps_remaining": iv.gaps_detected}

    @staticmethod
    def current_question(db: Session, creator_id: int, interview_id: int) -> dict | None:
        iv = CreatorService.get(db, creator_id, interview_id)
        return next_question(iv.gaps_detected or [], iv.answers or {})

    @staticmethod
    def get_spec(db: Session, creator_id: int, interview_id: int) -> dict:
        iv = CreatorService.get(db, creator_id, interview_id)
        if not iv.spec_draft:
            raise AppError(CONFLICT, "Answer the interview questions first", 409)
        return iv.spec_draft

    @staticmethod
    def update_spec(db: Session, creator_id: int, interview_id: int, updates: dict) -> dict:
        """Creator reviews TRUTH + key fixes — not a config marathon [PRD]."""
        iv = CreatorService.get(db, creator_id, interview_id)
        if not iv.spec_draft:
            raise AppError(CONFLICT, "No draft yet", 409)
        spec = dict(iv.spec_draft)
        spec.update({k: v for k, v in updates.items() if v is not None})
        iv.spec_draft = spec
        iv.updated_at = datetime.now(timezone.utc)
        db.commit()
        return spec

    # ---------- publish: create the real service from the spec ----------
    @staticmethod
    def publish(db: Session, creator_id: int, interview_id: int, visibility: str = "public") -> dict:
        from app.modules.qualification.engine import QualificationEngine
        from app.modules.service.service import ServiceRegistry

        iv = CreatorService.get(db, creator_id, interview_id)
        if not iv.spec_draft:
            raise AppError(CONFLICT, "No spec to publish", 409)

        spec = iv.spec_draft
        svc = ServiceRegistry.create(db, creator_id, {
            "name": spec.get("name", "Untitled Service"),
            "summary": spec.get("summary", ""),
            "description": spec.get("description", ""),
            "purpose": spec.get("purpose", ""),
            "audience": spec.get("audience", ""),
            "category": "general",
            "risk_level": spec.get("risk_classification", "LOW"),
            "intent_slugs": spec.get("intent_slugs", []),
            "capability_slugs": spec.get("capabilities", []),
        })
        version = ServiceRegistry.add_version(db, svc, {
            "purpose": spec.get("purpose", ""),
            "method": spec.get("method", ""),
            "behavior": spec.get("behavior", ""),
            "system_instructions": spec.get("system_instructions", ""),
            "boundaries": spec.get("boundaries", ""),
            "outcome_definition": spec.get("outcome_definition", {}),
            "model_requirements": {"reasoning": "medium", "structured_output": True},
            "context_requirements": spec.get("context_requirements", []),
            "knowledge_config": {"knowledge_version_id": spec.get("knowledge_version_id")},
            "tools_config": {},
            "examples": spec.get("examples", []),
        })

        # qualification gate before public visibility [PRD]
        qrun = QualificationEngine.run(db, svc.id, version.id, iv.id, spec)
        if qrun.result == "READY_TO_PUBLISH":
            # walk the lifecycle: draft → ready_for_test → testing → private → qualification_pending → ready → published
            for action in ("submit_test",):
                ServiceRegistry.lifecycle(db, svc, 0, action)
            svc = ServiceRegistry.get(db, svc.id)

            # direct transitions through the legal path
            ServiceRegistry._transition(db, svc, "testing", "auto test")
            ServiceRegistry._transition(db, svc, "qualification_pending", "auto qualification")
            ServiceRegistry._transition(db, svc, "ready", "qualification passed")
            ServiceRegistry._transition(db, svc, "published", "published via creator flow", actor_id=0)
            db.commit()
            iv.status = "published"
        else:
            iv.status = "qualified"
        iv.service_id = svc.id
        db.commit()
        return {
            "service_id": svc.id,
            "lifecycle_status": svc.lifecycle_status,
            "qualification": QualificationEngine.get_run(db, qrun.id),
        }
