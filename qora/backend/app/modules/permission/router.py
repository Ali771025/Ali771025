"""Permission router — API_CONTRACT §10."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.permission.schemas import GrantIn, GrantOut
from app.modules.permission.service import PermissionService
from app.shared.deps import get_current_user

router = APIRouter(prefix="/permissions", tags=["permission"])


@router.post("/grants", response_model=GrantOut, status_code=201)
def create_grant(data: GrantIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return PermissionService.grant(db, user.id, data.model_dump())


@router.get("/grants", response_model=list[GrantOut])
def list_grants(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return PermissionService.list_grants(db, user.id)


@router.delete("/grants/{grant_id}", status_code=204)
def revoke_grant(grant_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    PermissionService.revoke(db, user.id, grant_id)


@router.get("/audit")
def audit(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return {"items": PermissionService.audit(db, user.id)}
