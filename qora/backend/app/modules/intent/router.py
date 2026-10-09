"""Intent router — API_CONTRACT §5."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.intent.schemas import IntentCatalogItem, IntentResult
from app.modules.intent.service import IntentService
from app.shared.deps import get_current_user

router = APIRouter(prefix="/intents", tags=["intent"])


class AnalyzeIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@router.post("/analyze", response_model=IntentResult)
def analyze(data: AnalyzeIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return IntentService.analyze(db, user.id, data.text)


@router.get("", response_model=list[IntentCatalogItem])
def catalog(db: Session = Depends(get_db)):
    return IntentService.catalog(db)


history_router = APIRouter(prefix="/me/intents", tags=["intent"])


@history_router.get("/history")
def history(db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.modules.intent.models import UserIntentHistory
    from sqlalchemy import select

    rows = db.scalars(select(UserIntentHistory).where(UserIntentHistory.user_id == user.id).order_by(UserIntentHistory.occurred_at.desc()).limit(50)).all()
    return {"items": [{"intent_id": r.intent_id, "confidence": r.confidence, "entities": r.entities, "occurred_at": r.occurred_at} for r in rows]}


router.include_router(history_router)
