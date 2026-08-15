from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.domain import APIKey


@dataclass(frozen=True, slots=True)
class APIKeyPrincipal:
    key_id: str
    prefix: str
    tenant_id: str | None
    owner_user_id: str | None
    software_id: str | None
    version_id: str | None
    scopes: list[str]
    environment: str


class APIKeyAuthService:
    def authenticate(self, db: Session, raw_secret: str | None) -> APIKeyPrincipal | None:
        if not raw_secret:
            return None
        prefix = raw_secret[:8]
        candidates = list(db.scalars(select(APIKey).where(APIKey.prefix == prefix)))
        now = datetime.now(UTC)
        for key in candidates:
            if key.status not in {"active", "rotating"}:
                continue
            if key.expires_at and key.expires_at < now:
                continue
            if verify_password(raw_secret, key.secret_hash):
                key.last_used_at = now
                db.flush()
                return APIKeyPrincipal(
                    key_id=key.id,
                    prefix=key.prefix,
                    tenant_id=key.tenant_id,
                    owner_user_id=key.owner_user_id,
                    software_id=key.software_id,
                    version_id=key.version_id,
                    scopes=key.scopes or [],
                    environment=key.environment,
                )
        return None
