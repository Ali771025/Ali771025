"""Reputation API — separate creator/service trust and administrator event audit."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.reputation.service import ReputationService
from app.shared.audit import list_entries
from app.shared.deps import require_roles

router = APIRouter(prefix="/reputation", tags=["reputation"])


@router.get("/services/{service_id}/trust")
def service_trust(service_id: int, db: Session = Depends(get_db)):
    return ReputationService.trust_for(db, "service", service_id)


@router.get("/creators/{creator_id}/reputation")
def creator_reputation(creator_id: int, db: Session = Depends(get_db)):
    from app.modules.profile.service import ProfileService

    creator = ProfileService.get_creator_by_id(db, creator_id)
    return ReputationService.trust_for(
        db, "creator", creator_id, fallback=float(creator.trust_score) if creator else 0.5
    )


@router.get("/events")
def events(
    limit: int = Query(default=100, ge=1, le=250),
    kind: str | None = None,
    db: Session = Depends(get_db),
    admin=Depends(require_roles("admin")),
):
    return {"items": ReputationService.list_events(db, limit, kind)}


@router.get("/audit")
def audit(
    limit: int = Query(default=50, ge=1, le=200),
    action: str | None = None,
    db: Session = Depends(get_db),
    admin=Depends(require_roles("admin")),
):
    return {"items": list_entries(db, limit, action)}
