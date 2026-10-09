"""Identity router — API_CONTRACT §1."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.identity.schemas import LoginIn, RefreshIn, RegisterIn, SessionOut, TokenPair, UserOut
from app.modules.identity.service import IdentityService
from app.shared.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["identity"])


@router.post("/register", response_model=TokenPair, status_code=201)
def register(data: RegisterIn, request: Request, db: Session = Depends(get_db)):
    user = IdentityService.register(db, data.email, data.password, data.display_name, data.roles_wanted)
    from app.modules.identity.models import Device

    device = Device(user_id=user.id, platform="web")
    db.add(device)
    db.flush()
    tokens = IdentityService._issue_tokens(db, user, device, request.client.host if request.client else None, request.headers.get("user-agent"))
    return tokens


@router.post("/login", response_model=TokenPair)
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    return IdentityService.login(
        db, data.email, data.password, data.device_platform,
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )


@router.post("/refresh", response_model=TokenPair)
def refresh(data: RefreshIn, request: Request, db: Session = Depends(get_db)):
    return IdentityService.refresh(db, data.refresh_token, request.client.host if request.client else None, request.headers.get("user-agent"))


@router.post("/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    sid = request.headers.get("x-session-id")
    IdentityService.logout(db, user.id, int(sid) if sid and sid.isdigit() else None)


me_router = APIRouter(prefix="/me", tags=["identity"])


@me_router.get("", response_model=UserOut)
def me(user=Depends(get_current_user)):
    return user


@me_router.get("/sessions", response_model=list[SessionOut])
def sessions(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return IdentityService.list_sessions(db, user.id)


@me_router.delete("/sessions/{session_id}", status_code=204)
def revoke_session(session_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    IdentityService.logout(db, user.id, session_id)


# /me is a platform-level path (API_CONTRACT §1) — registered flat under /api/v1
me = me_router
