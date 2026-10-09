"""Knowledge router — API_CONTRACT §8 ('add my training material' UX)."""
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.knowledge.service import KnowledgeService
from app.modules.profile.service import ProfileService
from app.shared.deps import get_current_user

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class CollectionIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=500)


class SourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    source_date: datetime | None = None
    freshness_policy: str = Field(default="stale_after_90d")


def _creator(db, user):
    return ProfileService.get_creator_or_404(db, user.id)


@router.post("/collections", status_code=201)
def create_collection(data: CollectionIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = _creator(db, user)
    col = KnowledgeService.create_collection(db, c.id, data.name, data.description)
    return {"id": col.id, "name": col.name}


@router.get("/collections")
def list_collections(db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = _creator(db, user)
    return {"items": [{"id": x.id, "name": x.name} for x in KnowledgeService.list_collections(db, c.id)]}


@router.get("/collections/{collection_id}")
def collection_detail(collection_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = _creator(db, user)
    return KnowledgeService.collection_detail(db, collection_id, c.id)


@router.post("/collections/{collection_id}/sources", status_code=201)
def add_source(collection_id: int, data: SourceIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = _creator(db, user)
    src = KnowledgeService.add_source(db, collection_id, c.id, data.name, data.content,
                                      data.source_date, data.freshness_policy)
    return KnowledgeService.source_status(db, src.id)


@router.post("/collections/{collection_id}/versions", status_code=201)
def freeze_version(collection_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = _creator(db, user)
    v = KnowledgeService.freeze_version(db, collection_id, c.id)
    return {"id": v.id, "version_no": v.version_no, "snapshot": v.snapshot}


@router.get("/sources/{source_id}")
def source_status(source_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return KnowledgeService.source_status(db, source_id)
