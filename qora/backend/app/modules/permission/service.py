"""Permission service — grants, least-context resolution, audit [PRD]."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.permission.models import ContextGrant
from app.shared.errors import FORBIDDEN, AppError


class PermissionService:
    @staticmethod
    def grant(db: Session, user_id: int, data: dict) -> ContextGrant:
        # revoke previous grant of same type for the same service (latest wins)
        for g in db.scalars(
            select(ContextGrant).where(
                ContextGrant.user_id == user_id,
                ContextGrant.service_id == data["service_id"],
                ContextGrant.context_type == data["context_type"],
                ContextGrant.revoked_at.is_(None),
            )
        ).all():
            g.revoked_at = datetime.now(timezone.utc)
        g = ContextGrant(user_id=user_id, **data)
        db.add(g)
        db.commit()
        db.refresh(g)
        return g

    @staticmethod
    def revoke(db: Session, user_id: int, grant_id: int):
        g = db.get(ContextGrant, grant_id)
        if not g or g.user_id != user_id:
            raise AppError(FORBIDDEN, "Not your grant", 403)
        g.revoked_at = datetime.now(timezone.utc)
        db.commit()

    @staticmethod
    def list_grants(db: Session, user_id: int) -> list[ContextGrant]:
        return list(
            db.scalars(select(ContextGrant).where(ContextGrant.user_id == user_id).order_by(ContextGrant.granted_at.desc())).all()
        )

    @staticmethod
    def resolve(db: Session, user_id: int, service_id: int, context_types: list[str]) -> tuple[dict, list[str]]:
        """Returns (allowed_types, missing_types). ALLOW_ONCE is consumed here."""
        now = datetime.now(timezone.utc)
        allowed: dict[str, ContextGrant] = {}
        missing: list[str] = []
        for ct in context_types:
            g = db.scalar(
                select(ContextGrant).where(
                    ContextGrant.user_id == user_id,
                    ContextGrant.service_id == service_id,
                    ContextGrant.context_type == ct,
                    ContextGrant.revoked_at.is_(None),
                ).order_by(ContextGrant.granted_at.desc())
            )
            if not g:
                missing.append(ct)
                continue
            if g.expires_at and g.expires_at < now:
                missing.append(ct)
                continue
            if g.mode == "DENY":
                missing.append(ct)
                continue
            if g.mode == "ALLOW_ONCE":
                if g.consumed_at is not None:
                    missing.append(ct)
                    continue
                g.consumed_at = now  # consume-once [TECH]
            allowed[ct] = g
        db.commit()
        return {ct: g.scope for ct, g in allowed.items()}, missing

    @staticmethod
    def audit(db: Session, user_id: int) -> list[dict]:
        """What was shared, when, with whom — user-visible log."""
        return [
            {
                "grant_id": g.id,
                "service_id": g.service_id,
                "context_type": g.context_type,
                "mode": g.mode,
                "granted_at": g.granted_at,
                "consumed_at": g.consumed_at,
                "revoked_at": g.revoked_at,
            }
            for g in PermissionService.list_grants(db, user_id)
        ]
