"""Identity service — users, sessions, devices (API_CONTRACT §1)."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    hash_password,
    new_refresh_token,
    verify_password,
)
from app.modules.identity.models import Device, SessionRecord, User
from app.shared.errors import CONFLICT, FORBIDDEN, UNAUTHENTICATED, AppError


class IdentityService:
    # ---------- users ----------
    @staticmethod
    def get_user(db: Session, user_id: int) -> User | None:
        return db.get(User, user_id)

    @staticmethod
    def get_by_email(db: Session, email: str) -> User | None:
        return db.scalar(select(User).where(User.email == email.lower()))

    @staticmethod
    def register(db: Session, email: str, password: str, display_name: str, roles_wanted: list[str]) -> User:
        if IdentityService.get_by_email(db, email):
            raise AppError(CONFLICT, "Email already registered", 409)
        roles = [r for r in roles_wanted if r in ("consumer", "creator")] or ["consumer"]
        user = User(
            email=email.lower(),
            password_hash=hash_password(password),
            roles=",".join(sorted(set(roles))),
        )
        db.add(user)
        db.flush()
        from app.modules.profile.service import ProfileService  # interface import (boundary rule)

        ProfileService.create_private_profile(db, user.id, display_name)
        if "creator" in roles:
            ProfileService.create_creator_profile(db, user.id, display_name)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def login(db: Session, email: str, password: str, platform: str, ip: str | None, ua: str | None):
        user = IdentityService.get_by_email(db, email)
        if not user or not verify_password(password, user.password_hash):
            raise AppError(UNAUTHENTICATED, "Invalid email or password", 401)
        if user.account_status != "active":
            raise AppError(FORBIDDEN, f"Account is {user.account_status}", 403)
        device = Device(user_id=user.id, platform=platform)
        db.add(device)
        db.flush()
        return IdentityService._issue_tokens(db, user, device, ip, ua)

    @staticmethod
    def _issue_tokens(db: Session, user: User, device: Device, ip, ua):
        access = create_access_token(str(user.id), {"roles": user.roles})
        raw_refresh, refresh_hash = new_refresh_token()
        session = SessionRecord(
            user_id=user.id,
            device_id=device.id,
            refresh_token_hash=refresh_hash,
            ip=ip,
            user_agent=(ua or "")[:255] or None,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db.add(session)
        device.last_seen_at = datetime.now(timezone.utc)
        db.commit()
        return {
            "access_token": access,
            "refresh_token": raw_refresh,
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    @staticmethod
    def refresh(db: Session, raw_refresh: str, ip, ua):
        now = datetime.now(timezone.utc)
        for s in db.scalars(
            select(SessionRecord).where(SessionRecord.revoked_at.is_(None), SessionRecord.expires_at > now)
        ).all():
            if verify_password(raw_refresh, s.refresh_token_hash):
                s.revoked_at = now  # rotation [TECH]
                db.flush()
                user = db.get(User, s.user_id)
                device = db.get(Device, s.device_id) if s.device_id else Device(user_id=user.id, platform="web")
                if not s.device_id:
                    db.add(device)
                    db.flush()
                return IdentityService._issue_tokens(db, user, device, ip, ua)
        raise AppError(UNAUTHENTICATED, "Invalid refresh token", 401)

    @staticmethod
    def logout(db: Session, user_id: int, session_id: int | None = None):
        q = select(SessionRecord).where(SessionRecord.user_id == user_id, SessionRecord.revoked_at.is_(None))
        if session_id:
            q = q.where(SessionRecord.id == session_id)
        for s in db.scalars(q).all():
            s.revoked_at = datetime.now(timezone.utc)
        db.commit()

    @staticmethod
    def list_sessions(db: Session, user_id: int) -> list[SessionRecord]:
        return list(
            db.scalars(
                select(SessionRecord)
                .where(SessionRecord.user_id == user_id, SessionRecord.revoked_at.is_(None))
                .order_by(SessionRecord.created_at.desc())
            ).all()
        )
