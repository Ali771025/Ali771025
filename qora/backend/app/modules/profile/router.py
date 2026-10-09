"""Profile router — API_CONTRACT §2. Public endpoints use CreatorPublic ONLY."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.profile.schemas import (
    CreatorProfileOut,
    CreatorProfileUpdate,
    CreatorPublic,
    PrivateProfileOut,
    PrivateProfileUpdate,
)
from app.modules.profile.service import ProfileService
from app.shared.deps import get_current_user

router = APIRouter(tags=["profile"])


@router.get("/me/profile/private", response_model=PrivateProfileOut)
def get_private(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return ProfileService.get_private(db, user.id)


@router.patch("/me/profile/private", response_model=PrivateProfileOut)
def update_private(data: PrivateProfileUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return ProfileService.update_private(db, user.id, data.model_dump(exclude_unset=True))


@router.get("/me/profile/creator", response_model=CreatorProfileOut)
def get_creator(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return ProfileService.get_creator_or_404(db, user.id)


@router.patch("/me/profile/creator", response_model=CreatorProfileOut)
def update_creator(data: CreatorProfileUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return ProfileService.update_creator(db, user.id, data.model_dump(exclude_unset=True))


@router.post("/me/profile/creator", response_model=CreatorProfileOut, status_code=201)
def create_creator(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Upgrade a consumer account to also be a creator [PRD: one user, many hats]."""
    existing = ProfileService.get_creator(db, user.id)
    if existing:
        return existing
    p = ProfileService.create_creator_profile(db, user.id, user.email.split("@")[0])
    if not user.has_role("creator"):
        user.roles = user.roles + ",creator"
    db.commit()
    db.refresh(p)
    return p


@router.post("/me/profile/creator/verification", response_model=CreatorProfileOut)
def request_verification(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return ProfileService.request_verification(db, user.id)


@router.get("/creators/{user_id}", response_model=CreatorPublic)
def public_creator(user_id: int, db: Session = Depends(get_db)):
    """Public projection — private fields can never appear here [PRD]."""
    return ProfileService.public_creator(db, user_id)
