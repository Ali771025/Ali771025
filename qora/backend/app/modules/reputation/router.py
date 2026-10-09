"""Reputation router — API_CONTRACT §13."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.reputation.service import ReputationService
from app.shared.deps import get_current_user

router = APIRouter(prefix="/reputation", tags=["reputation"])


@router.get("/services/{service_id}/trust")
def service_trust(service_id: int, db: Session = Depends(get_db)):
    return ReputationService.trust_for(db, "service", service_id)


@router.get("/creators/{creator_id}/reputation")
def creator_reputation(creator_id: int, db: Session = Depends(get_db)):
    return ReputationService.trust_for(db, "creator", creator_id)
