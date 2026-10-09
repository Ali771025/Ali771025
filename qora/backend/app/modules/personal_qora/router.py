"""Personal QORA router — API_CONTRACT §3."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.personal_qora.schemas import GoalIn, GoalOut, JourneyOut, MemoryIn, MemoryOut
from app.modules.personal_qora.service import PersonalQoraService
from app.shared.deps import get_current_user

router = APIRouter(prefix="/me", tags=["personal_qora"])


@router.get("/memories", response_model=list[MemoryOut])
def list_memories(kind: str | None = Query(default=None), db: Session = Depends(get_db), user=Depends(get_current_user)):
    return PersonalQoraService.list_memories(db, user.id, kind)


@router.post("/memories", response_model=MemoryOut, status_code=201)
def add_memory(data: MemoryIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return PersonalQoraService.add_memory(db, user.id, data.model_dump(), source="user", confidence=1.0)


@router.patch("/memories/{memory_id}", response_model=MemoryOut)
def update_memory(memory_id: int, data: MemoryIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return PersonalQoraService.update_memory(db, user.id, memory_id, data.model_dump())


@router.delete("/memories/{memory_id}", status_code=204)
def forget(memory_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    PersonalQoraService.forget(db, user.id, memory_id)


@router.get("/goals", response_model=list[GoalOut])
def list_goals(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return PersonalQoraService.list_goals(db, user.id)


@router.post("/goals", response_model=GoalOut, status_code=201)
def add_goal(data: GoalIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return PersonalQoraService.add_goal(db, user.id, data.model_dump())


@router.patch("/goals/{goal_id}", response_model=GoalOut)
def update_goal(goal_id: int, data: GoalIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return PersonalQoraService.update_goal(db, user.id, goal_id, data.model_dump())


@router.get("/journeys", response_model=list[JourneyOut])
def list_journeys(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return PersonalQoraService.list_journeys(db, user.id)


@router.get("/journeys/{journey_id}", response_model=JourneyOut)
def get_journey(journey_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return PersonalQoraService.get_journey(db, user.id, journey_id)


@router.get("/context")
def get_context(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """What QORA understands about you (rendered) — 'My QORA' page."""
    return PersonalQoraService.context_summary(db, user.id)
