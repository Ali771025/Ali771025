"""Service registry router — API_CONTRACT §6."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.service.schemas import (
    DiscoveryItem,
    LifecycleAction,
    ServiceCreate,
    ServiceOut,
    VersionCreate,
    VersionOut,
)
from app.modules.service.service import ServiceRegistry
from app.shared.deps import get_current_user

router = APIRouter(prefix="/services", tags=["service"])


@router.get("", response_model=list[DiscoveryItem])
def discover(
    q: str | None = Query(default=None),
    intent: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    items = ServiceRegistry.discover(db, user.id, query_intent_slug=intent, q=q, limit=limit)
    for it in items:
        it["service"] = ServiceOut.model_validate(it["service"])
    return items


@router.get("/{service_id}", response_model=ServiceOut)
def get_service(service_id: int, db: Session = Depends(get_db)):
    return ServiceRegistry.get(db, service_id)


@router.get("/{service_id}/versions", response_model=list[VersionOut])
def versions(service_id: int, db: Session = Depends(get_db)):
    return ServiceRegistry.versions_of(db, service_id)


@router.post("", response_model=ServiceOut, status_code=201)
def create_service(data: ServiceCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.modules.profile.service import ProfileService
    from app.shared.errors import FORBIDDEN, AppError

    if not user.has_role("creator"):
        raise AppError(FORBIDDEN, "Creator role required (POST /me/profile/creator first)", 403)
    creator = ProfileService.get_creator_or_404(db, user.id)
    return ServiceRegistry.create(db, creator.id, data.model_dump())


@router.post("/{service_id}/versions", response_model=VersionOut, status_code=201)
def add_version(service_id: int, data: VersionCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.modules.profile.service import ProfileService

    creator = ProfileService.get_creator_or_404(db, user.id)
    svc = ServiceRegistry.owned(db, service_id, creator.id)
    return ServiceRegistry.add_version(db, svc, data.model_dump())


@router.post("/{service_id}/lifecycle", response_model=ServiceOut)
def lifecycle(service_id: int, data: LifecycleAction, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.modules.profile.service import ProfileService

    creator = ProfileService.get_creator_or_404(db, user.id)
    svc = ServiceRegistry.owned(db, service_id, creator.id)
    return ServiceRegistry.lifecycle(db, svc, user.id, data.action, data.reason)


@router.post("/{service_id}/follow", status_code=204)
def follow(service_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ServiceRegistry.get(db, service_id)
    ServiceRegistry.follow(db, user.id, service_id, True)


@router.delete("/{service_id}/follow", status_code=204)
def unfollow(service_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ServiceRegistry.follow(db, user.id, service_id, False)
