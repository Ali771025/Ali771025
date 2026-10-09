"""Service registry router — discovery, lifecycle, admin ranking and risk verification."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
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
from app.shared.deps import get_current_user, require_roles

router = APIRouter(prefix="/services", tags=["service"])


class RankingWeightsIn(BaseModel):
    intent_relevance: float = Field(ge=0, le=1)
    outcome_quality: float = Field(ge=0, le=1)
    personal_fit: float = Field(ge=0, le=1)
    trust: float = Field(ge=0, le=1)
    freshness: float = Field(ge=0, le=1)
    exploration: float = Field(ge=0, le=1)
    satisfaction: float = Field(ge=0, le=1)
    repeat_use: float = Field(ge=0, le=1)


class VerificationIn(BaseModel):
    status: str = Field(pattern="^(pending|verified|rejected)$")


# Static admin paths precede the integer service-id routes.
@router.get("/admin/ranking-weights")
def get_ranking_weights(db: Session = Depends(get_db), admin=Depends(require_roles("admin"))):
    return {"weights": ServiceRegistry.rank_weights(db)}


@router.put("/admin/ranking-weights")
def update_ranking_weights(
    data: RankingWeightsIn,
    db: Session = Depends(get_db),
    admin=Depends(require_roles("admin")),
):
    return {"weights": ServiceRegistry.update_rank_weights(db, admin.id, data.model_dump())}


@router.post("/admin/services/{service_id}/verification", response_model=ServiceOut)
def verify_service(
    service_id: int,
    data: VerificationIn,
    db: Session = Depends(get_db),
    admin=Depends(require_roles("admin")),
):
    return ServiceRegistry.set_verification_status(db, service_id, admin.id, data.status)


@router.get("", response_model=list[DiscoveryItem])
def discover(
    q: str | None = Query(default=None),
    intent: str | None = Query(default=None),
    capability: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if capability:
        items = ServiceRegistry.by_capability(db, capability, limit=limit)
        if q:
            needle = q.lower()
            items = [item for item in items if needle in (
                item["service"].name + item["service"].summary + item["service"].description
            ).lower()]
        if intent:
            ranked = ServiceRegistry.discover(db, user.id, query_intent_slug=intent, q=q, limit=50)
            allowed = {item["service"].id for item in items}
            items = [item for item in ranked if item["service"].id in allowed][:limit]
    else:
        items = ServiceRegistry.discover(db, user.id, query_intent_slug=intent, q=q, limit=limit)
    for item in items:
        item["service"] = ServiceOut.model_validate(item["service"])
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
    service = ServiceRegistry.owned(db, service_id, creator.id)
    return ServiceRegistry.add_version(db, service, data.model_dump())


@router.post("/{service_id}/lifecycle", response_model=ServiceOut)
def lifecycle(service_id: int, data: LifecycleAction, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.modules.profile.service import ProfileService

    creator = ProfileService.get_creator_or_404(db, user.id)
    service = ServiceRegistry.owned(db, service_id, creator.id)
    return ServiceRegistry.lifecycle(db, service, user.id, data.action, data.reason)


@router.post("/{service_id}/follow", status_code=204)
def follow(service_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ServiceRegistry.get(db, service_id)
    ServiceRegistry.follow(db, user.id, service_id, True)


@router.delete("/{service_id}/follow", status_code=204)
def unfollow(service_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ServiceRegistry.follow(db, user.id, service_id, False)
