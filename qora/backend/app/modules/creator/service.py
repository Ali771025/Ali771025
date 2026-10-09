"""Creator Platform service — interview lifecycle + risk-aware publishing."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.creator.interview import detect_gaps, generate_spec, next_question
from app.modules.creator.models import CreatorInterview
from app.shared.errors import CONFLICT, FORBIDDEN, NOT_FOUND, AppError


class CreatorService:
    @staticmethod
    def start(db: Session, creator_id: int, intent_statement: str) -> CreatorInterview:
        interview = CreatorInterview(
            creator_id=creator_id,
            intent_statement=intent_statement.strip(),
            gaps_detected=detect_gaps(intent_statement),
            answers={},
        )
        db.add(interview)
        db.commit()
        db.refresh(interview)
        return interview

    @staticmethod
    def get(db: Session, creator_id: int, interview_id: int) -> CreatorInterview:
        interview = db.get(CreatorInterview, interview_id)
        if not interview:
            raise AppError(NOT_FOUND, "Interview not found", 404)
        if interview.creator_id != creator_id:
            raise AppError(FORBIDDEN, "Not your interview", 403)
        return interview

    @staticmethod
    def list_for(db: Session, creator_id: int) -> list[CreatorInterview]:
        return list(db.scalars(
            select(CreatorInterview)
            .where(CreatorInterview.creator_id == creator_id)
            .order_by(CreatorInterview.created_at.desc())
        ).all())

    @staticmethod
    def answer(db: Session, creator_id: int, interview_id: int, answers: list[dict]) -> dict:
        interview = CreatorService.get(db, creator_id, interview_id)
        stored = dict(interview.answers or {})
        for answer in answers:
            stored[answer["question_id"]] = answer.get("text", "")
        interview.answers = stored
        interview.updated_at = datetime.now(timezone.utc)
        question = next_question(interview.gaps_detected or [], stored)
        if question is None:
            interview.spec_draft = generate_spec(interview.intent_statement, stored)
            interview.status = "spec_ready"
            db.commit()
            return {"next_question": None, "interview_complete": True, "spec_draft": interview.spec_draft}
        db.commit()
        return {"next_question": question, "interview_complete": False, "gaps_remaining": interview.gaps_detected}

    @staticmethod
    def current_question(db: Session, creator_id: int, interview_id: int) -> dict | None:
        interview = CreatorService.get(db, creator_id, interview_id)
        return next_question(interview.gaps_detected or [], interview.answers or {})

    @staticmethod
    def get_spec(db: Session, creator_id: int, interview_id: int) -> dict:
        interview = CreatorService.get(db, creator_id, interview_id)
        if not interview.spec_draft:
            raise AppError(CONFLICT, "Answer the interview questions first", 409)
        return interview.spec_draft

    @staticmethod
    def update_spec(db: Session, creator_id: int, interview_id: int, updates: dict) -> dict:
        """Creator reviews truth and important corrections, not a configuration marathon [PRD]."""
        interview = CreatorService.get(db, creator_id, interview_id)
        if not interview.spec_draft:
            raise AppError(CONFLICT, "No draft yet", 409)
        specification = dict(interview.spec_draft)
        specification.update({key: value for key, value in updates.items() if value is not None})
        interview.spec_draft = specification
        interview.updated_at = datetime.now(timezone.utc)
        db.commit()
        return specification

    @staticmethod
    def publish(db: Session, creator_id: int, interview_id: int, visibility: str = "public") -> dict:
        from app.modules.profile.service import ProfileService
        from app.modules.qualification.engine import QualificationEngine
        from app.modules.service.risk import RiskService
        from app.modules.service.service import ServiceRegistry

        interview = CreatorService.get(db, creator_id, interview_id)
        if not interview.spec_draft:
            raise AppError(CONFLICT, "No spec to publish", 409)
        spec = interview.spec_draft
        service = ServiceRegistry.create(db, creator_id, {
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
        version = ServiceRegistry.add_version(db, service, {
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

        # Re-run qualification against platform-classified risk, not just creator self-report.
        qualification_spec = {**spec, "risk_classification": service.risk_level}
        qrun = QualificationEngine.run(db, service.id, version.id, interview.id, qualification_spec)
        publication_blockers: list[str] = []
        if qrun.result == "READY_TO_PUBLISH":
            ServiceRegistry.lifecycle(db, service, 0, "submit_test", "creator qualification")
            service = ServiceRegistry.get(db, service.id)
            ServiceRegistry._transition(db, service, "testing", "automatic qualification test")
            ServiceRegistry._transition(db, service, "qualification_pending", "qualification passed")
            ServiceRegistry._transition(db, service, "ready", "qualified and ready for publication")
            creator = ProfileService.get_creator_by_id(db, creator_id)
            publication_blockers = RiskService.publication_blockers(service, creator, version)
            if not publication_blockers:
                ServiceRegistry._transition(db, service, "published", "published via creator flow", actor_id=0)
                interview.status = "published"
            else:
                # Keep a qualified high-risk service private until the platform verifies it.
                interview.status = "qualified"
        else:
            interview.status = "qualified"
        interview.service_id = service.id
        db.commit()
        return {
            "service_id": service.id,
            "lifecycle_status": service.lifecycle_status,
            "publication_blockers": publication_blockers,
            "qualification": QualificationEngine.get_run(db, qrun.id),
        }
