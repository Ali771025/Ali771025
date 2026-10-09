"""Profile service — strict separation of private and public identity [PRD]."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.profile.models import CreatorProfile, PrivateProfile
from app.shared.errors import FORBIDDEN, NOT_FOUND, AppError


class ProfileService:
    # ---------- creation (called by identity) ----------
    @staticmethod
    def create_private_profile(db: Session, user_id: int, display_name: str) -> PrivateProfile:
        p = PrivateProfile(user_id=user_id, display_name=display_name)
        db.add(p)
        return p

    @staticmethod
    def create_creator_profile(db: Session, user_id: int, display_name: str) -> CreatorProfile:
        p = CreatorProfile(user_id=user_id, display_name=display_name)
        db.add(p)
        return p

    # ---------- private (owner only) ----------
    @staticmethod
    def get_private(db: Session, user_id: int) -> PrivateProfile:
        p = db.scalar(select(PrivateProfile).where(PrivateProfile.user_id == user_id))
        if not p:
            raise AppError(NOT_FOUND, "Private profile not found", 404)
        return p

    @staticmethod
    def update_private(db: Session, user_id: int, data: dict) -> PrivateProfile:
        p = ProfileService.get_private(db, user_id)
        for k, v in data.items():
            if v is not None:
                setattr(p, k, v)
        db.commit()
        db.refresh(p)
        return p

    # ---------- creator ----------
    @staticmethod
    def get_creator(db: Session, user_id: int) -> CreatorProfile | None:
        return db.scalar(select(CreatorProfile).where(CreatorProfile.user_id == user_id))

    @staticmethod
    def get_creator_or_404(db: Session, user_id: int) -> CreatorProfile:
        p = ProfileService.get_creator(db, user_id)
        if not p:
            raise AppError(NOT_FOUND, "Creator profile not found", 404)
        return p

    @staticmethod
    def update_creator(db: Session, user_id: int, data: dict) -> CreatorProfile:
        p = ProfileService.get_creator_or_404(db, user_id)
        for k, v in data.items():
            if v is not None:
                setattr(p, k, v)
        db.commit()
        db.refresh(p)
        return p

    @staticmethod
    def request_verification(db: Session, user_id: int) -> CreatorProfile:
        p = ProfileService.get_creator_or_404(db, user_id)
        if p.verification_status == "none":
            p.verification_status = "pending"
        db.commit()
        db.refresh(p)
        return p

    # ---------- public projection (the only leak-safe serializer) ----------
    @staticmethod
    def public_creator(db: Session, user_id: int) -> CreatorProfile:
        return ProfileService.get_creator_or_404(db, user_id)

    @staticmethod
    def get_creator_by_id(db: Session, creator_profile_id: int) -> CreatorProfile | None:
        return db.get(CreatorProfile, creator_profile_id)

    @staticmethod
    def assert_owner(profile_user_id: int, user_id: int):
        if profile_user_id != user_id:
            raise AppError(FORBIDDEN, "Not your profile", 403)
