"""Analytics router — API_CONTRACT §14 (creator view)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.analytics.service import AnalyticsService
from app.shared.deps import get_current_user

router = APIRouter(prefix="/creator/analytics", tags=["analytics"])


@router.get("/overview")
def overview(db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.modules.profile.service import ProfileService

    c = ProfileService.get_creator_or_404(db, user.id)
    return AnalyticsService.overview(db, c.id)


@router.get("/services/{service_id}/metrics")
def metrics(service_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.modules.profile.service import ProfileService

    c = ProfileService.get_creator_or_404(db, user.id)
    return AnalyticsService.service_metrics(db, c.id, service_id)


@router.get("/services/{service_id}/insights")
def insights(service_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.modules.profile.service import ProfileService

    c = ProfileService.get_creator_or_404(db, user.id)
    return {"items": AnalyticsService.insights(db, c.id, service_id)}
