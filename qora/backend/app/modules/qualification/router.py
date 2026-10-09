"""Qualification router — API_CONTRACT §12 (+ simulation jobs)."""
from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db, SessionLocal
from app.modules.qualification.engine import QualificationEngine
from app.modules.qualification.simulation import SimulationEngine
from app.shared.deps import get_current_user
from app.shared.errors import NOT_FOUND, AppError

router = APIRouter(prefix="/qualification", tags=["qualification"])


class QualifyIn(BaseModel):
    service_id: int
    service_version_id: int | None = None
    interview_id: int | None = None
    spec: dict


class SimulateIn(BaseModel):
    service_id: int
    interview_id: int | None = None
    spec: dict


def _run_simulation(service_id: int, interview_id: int | None, spec: dict, run_id_out: dict):
    db = SessionLocal()
    try:
        run = SimulationEngine.run(db, service_id, interview_id, spec)
        run_id_out["id"] = run.id
    finally:
        db.close()


@router.post("/simulate", status_code=202)
def simulate(data: SimulateIn, background: BackgroundTasks, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Runs the 7-scenario suite as a background job [TECH: async jobs]."""
    out: dict = {}
    background.add_task(_run_simulation, data.service_id, data.interview_id, data.spec, out)
    return {"status": "queued", "detail": "poll GET /qualification/simulations/{id} — the first run id appears in the creator console"}

@router.post("/simulate/sync", status_code=201)
def simulate_sync(data: SimulateIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Synchronous variant (used by tests and the creator console for instant feedback)."""
    run = SimulationEngine.run(db, data.service_id, data.interview_id, data.spec)
    return SimulationEngine.get_run(db, run.id)


@router.get("/simulations/{run_id}")
def simulation_run(run_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    data = SimulationEngine.get_run(db, run_id)
    if not data:
        raise AppError(NOT_FOUND, "Simulation run not found", 404)
    return data


@router.post("/runs", status_code=201)
def qualify(data: QualifyIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    qrun = QualificationEngine.run(db, data.service_id, data.service_version_id, data.interview_id, data.spec)
    return QualificationEngine.get_run(db, qrun.id)


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    data = QualificationEngine.get_run(db, run_id)
    if not data:
        raise AppError(NOT_FOUND, "Qualification run not found", 404)
    return data
