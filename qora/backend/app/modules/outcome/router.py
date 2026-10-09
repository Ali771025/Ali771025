"""Outcome router — API_CONTRACT §11."""
from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.outcome.models import OutcomeRecord
from app.modules.outcome.service import OutcomeService
from app.modules.analytics.tasks import aggregate_service_day
from app.shared.deps import get_current_user

router = APIRouter(tags=["outcome"])


class ConfirmIn(BaseModel):
    useful: bool = True
    achieved_goal: bool = True
    notes: str = Field(default="", max_length=2000)
    signals: dict = Field(default_factory=dict)


@router.post("/sessions/{session_id}/outcome/confirm")
def confirm(
    session_id: int,
    data: ConfirmIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    result = OutcomeService.confirm(db, user.id, session_id, data.model_dump())
    background_tasks.add_task(aggregate_service_day, result.service_id)
    return result


@router.get("/sessions/{session_id}/outcome")
def get_outcome(session_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    rec = OutcomeService.session_outcome(db, session_id)
    if not rec or rec.user_id != user.id:
        from app.shared.errors import NOT_FOUND, AppError

        raise AppError(NOT_FOUND, "Outcome not found", 404)
    return {
        "session_id": rec.session_id,
        "status": rec.status,
        "score": rec.score,
        "signals": rec.signals,
        "user_confirmed": rec.user_confirmed,
    }


@router.get("/services/{service_id}/outcomes")
def service_outcomes(service_id: int, db: Session = Depends(get_db)):
    stats = OutcomeService.get_service_outcome_stats(db).get(service_id, {})
    return {"service_id": service_id, **stats}
