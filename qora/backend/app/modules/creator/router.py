"""Creator router — API_CONTRACT §7 (the no-code creation flow)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.creator.service import CreatorService
from app.modules.profile.service import ProfileService
from app.shared.deps import get_current_user

router = APIRouter(prefix="/creator", tags=["creator"])


class InterviewStart(BaseModel):
    intent_statement: str = Field(min_length=5, max_length=2000)


class AnswersIn(BaseModel):
    answers: list[dict] = Field(default_factory=list)  # [{question_id, text}]


class SpecUpdate(BaseModel):
    name: str | None = None
    summary: str | None = None
    description: str | None = None
    purpose: str | None = None
    audience: str | None = None
    method: str | None = None
    behavior: str | None = None
    system_instructions: str | None = None
    boundaries: str | None = None
    outcome_definition: dict | None = None
    knowledge_version_id: int | None = None
    risk_classification: str | None = None


class PublishIn(BaseModel):
    visibility: str = Field(default="public", pattern="^(private|unlisted|public)$")


def _creator(db, user):
    if not user.has_role("creator"):
        from app.shared.errors import FORBIDDEN, AppError

        raise AppError(FORBIDDEN, "Creator role required (POST /me/profile/creator first)", 403)
    return ProfileService.get_creator_or_404(db, user.id)


# ---------- interviews ----------
@router.post("/interviews", status_code=201)
def start_interview(data: InterviewStart, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = _creator(db, user)
    iv = CreatorService.start(db, c.id, data.intent_statement)
    return {
        "id": iv.id,
        "status": iv.status,
        "gaps_detected": iv.gaps_detected,
        "next_question": CreatorService.current_question(db, c.id, iv.id),
    }


@router.get("/interviews")
def list_interviews(db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = _creator(db, user)
    return {
        "items": [
            {"id": iv.id, "intent_statement": iv.intent_statement, "status": iv.status, "service_id": iv.service_id}
            for iv in CreatorService.list_for(db, c.id)
        ]
    }


@router.get("/interviews/{interview_id}")
def get_interview(interview_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = _creator(db, user)
    iv = CreatorService.get(db, c.id, interview_id)
    return {
        "id": iv.id,
        "intent_statement": iv.intent_statement,
        "status": iv.status,
        "gaps_detected": iv.gaps_detected,
        "answers": iv.answers,
        "next_question": CreatorService.current_question(db, c.id, iv.id) if iv.status == "interviewing" else None,
        "service_id": iv.service_id,
    }


@router.post("/interviews/{interview_id}/answers")
def answer(interview_id: int, data: AnswersIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = _creator(db, user)
    return CreatorService.answer(db, c.id, interview_id, data.answers)


# ---------- spec ----------
@router.get("/interviews/{interview_id}/spec")
def get_spec(interview_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = _creator(db, user)
    return CreatorService.get_spec(db, c.id, interview_id)


@router.patch("/interviews/{interview_id}/spec")
def update_spec(interview_id: int, data: SpecUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = _creator(db, user)
    return CreatorService.update_spec(db, c.id, interview_id, data.model_dump(exclude_unset=True))


# ---------- simulate / qualify / publish ----------
@router.post("/interviews/{interview_id}/simulate", status_code=201)
def simulate(interview_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.modules.qualification.simulation import SimulationEngine

    c = _creator(db, user)
    iv = CreatorService.get(db, c.id, interview_id)
    spec = CreatorService.get_spec(db, c.id, interview_id)
    run = SimulationEngine.run(db, iv.service_id or -(iv.id), iv.id, spec)
    iv.status = "simulated"
    db.commit()
    return SimulationEngine.get_run(db, run.id)


@router.post("/interviews/{interview_id}/qualify", status_code=201)
def qualify(interview_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.modules.qualification.engine import QualificationEngine

    c = _creator(db, user)
    iv = CreatorService.get(db, c.id, interview_id)
    spec = CreatorService.get_spec(db, c.id, interview_id)
    qrun = QualificationEngine.run(db, iv.service_id or -(iv.id), None, iv.id, spec)
    iv.status = "qualified"
    db.commit()
    return QualificationEngine.get_run(db, qrun.id)


@router.get("/qualifications/{run_id}")
def qualification(run_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.modules.qualification.engine import QualificationEngine
    from app.shared.errors import NOT_FOUND, AppError

    data = QualificationEngine.get_run(db, run_id)
    if not data:
        raise AppError(NOT_FOUND, "Qualification run not found", 404)
    return data


@router.post("/interviews/{interview_id}/publish", status_code=201)
def publish(interview_id: int, data: PublishIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = _creator(db, user)
    return CreatorService.publish(db, c.id, interview_id, data.visibility)
