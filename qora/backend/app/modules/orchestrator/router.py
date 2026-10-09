"""Orchestration API — plan and run multi-service chains."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.orchestrator.service import OrchestratorService
from app.shared.deps import get_current_user

router = APIRouter(prefix="/orchestration", tags=["orchestration"])


class PlanIn(BaseModel):
    goal_text: str = Field(min_length=3)


@router.post("/plans")
def create_plan(data: PlanIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return OrchestratorService.plan(db, user.id, data.goal_text)


@router.get("/plans")
def list_plans(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return {"items": OrchestratorService.list_for(db, user.id)}


@router.get("/plans/{plan_id}")
def get_plan(plan_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return OrchestratorService.get(db, user.id, plan_id)


@router.post("/plans/{plan_id}/execute")
def execute_plan(plan_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return OrchestratorService.execute(db, user.id, plan_id)
