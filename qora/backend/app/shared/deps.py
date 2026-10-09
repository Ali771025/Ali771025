"""Shared FastAPI dependencies (auth)."""
from fastapi import Depends, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_token
from app.shared.errors import FORBIDDEN, UNAUTHENTICATED, AppError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    from app.modules.identity.service import IdentityService

    if not token:
        raise AppError(UNAUTHENTICATED, "Not authenticated", 401)
    payload = decode_token(token)
    if not payload or payload.get("type") != "access" or "sub" not in payload:
        raise AppError(UNAUTHENTICATED, "Invalid or expired token", 401)
    user = IdentityService.get_user(db, int(payload["sub"]))
    if not user:
        raise AppError(UNAUTHENTICATED, "Account unavailable", 401)
    if user.account_status != "active":
        raise AppError(FORBIDDEN, f"Account is {user.account_status}", 403)
    return user


def require_roles(*roles: str):
    def checker(user=Depends(get_current_user)):
        if not any(user.has_role(r) for r in roles):
            raise AppError(FORBIDDEN, "Insufficient permissions", 403)
        return user

    return checker


def trace_from_header(x_trace_id: str | None = Header(default=None)) -> str:
    from app.shared.logging import get_trace_id, new_trace_id, set_trace_id

    if x_trace_id:
        set_trace_id(x_trace_id)
        return x_trace_id
    return get_trace_id() if get_trace_id() != "-" else new_trace_id()
