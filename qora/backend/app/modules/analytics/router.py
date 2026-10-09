"""Analytics router — creator dashboards, daily aggregation and insight inbox."""
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.analytics.service import AnalyticsService
from app.modules.profile.service import ProfileService
from app.shared.deps import get_current_user

router = APIRouter(prefix="/creator/analytics", tags=["analytics"])


class AggregateIn(BaseModel):
    bucket_date: date | None = None


def _creator(db, user):
    return ProfileService.get_creator_or_404(db, user.id)


@router.get("/overview")
def overview(db: Session = Depends(get_db), user=Depends(get_current_user)):
    creator = _creator(db, user)
    return AnalyticsService.overview(db, creator.id)


@router.post("/aggregate")
def aggregate(data: AggregateIn | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    creator = _creator(db, user)
    return AnalyticsService.aggregate_day(db, (data or AggregateIn()).bucket_date, creator.id)


@router.get("/insights")
def insight_inbox(db: Session = Depends(get_db), user=Depends(get_current_user)):
    creator = _creator(db, user)
    return {"items": AnalyticsService.insight_inbox(db, creator.id)}


@router.post("/insights/{insight_id}/dismiss")
def dismiss_insight(insight_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    creator = _creator(db, user)
    return AnalyticsService.mark_insight(db, creator.id, insight_id, "dismissed")


@router.post("/insights/{insight_id}/acted-on")
def mark_insight_acted(insight_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    creator = _creator(db, user)
    return AnalyticsService.mark_insight(db, creator.id, insight_id, "acted_on")


@router.get("/services/{service_id}/metrics")
def metrics(service_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    creator = _creator(db, user)
    return AnalyticsService.service_metrics(db, creator.id, service_id)


@router.get("/services/{service_id}/insights")
def insights(service_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    creator = _creator(db, user)
    return {"items": AnalyticsService.insights(db, creator.id, service_id)}
