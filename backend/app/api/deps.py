from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.common.context import ActorContext
from app.core.security import decode_token
from app.db.session import get_db
from app.models.domain import User

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(slots=True)
class CurrentUser:
    id: str
    username: str
    tenant_id: str | None
    roles: list[str]
    scopes: list[str]


DbSession = Annotated[Session, Depends(get_db)]


async def get_current_user(
    request: Request,
    db: DbSession,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> CurrentUser:
    """Resolve current user from JWT. Local dev accepts X-Dev-User for first bootstrap."""

    if credentials:
        try:
            payload = decode_token(credentials.credentials)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")
        user = db.get(User, user_id)
    else:
        dev_user = request.headers.get("X-Dev-User")
        if not dev_user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        user = db.scalar(select(User).where(User.username == dev_user))

    if not user or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or unknown user")

    return CurrentUser(
        id=user.id,
        username=user.username,
        tenant_id=user.tenant_id,
        roles=user.roles or [],
        scopes=user.scopes or [],
    )


def actor_context_from_request(request: Request, current_user: CurrentUser) -> ActorContext:
    return ActorContext(
        actor_id=current_user.id,
        tenant_id=current_user.tenant_id,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        correlation_id=getattr(request.state, "correlation_id", request.headers.get("x-correlation-id")),
    )
