"""Auth routes: register, login, me."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.base import get_db
from app.db.models import User, Wallet
from app.schemas.schemas import LoginIn, RegisterIn, Token, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

AVATAR_COLORS = ["#6366f1", "#0ea5e9", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6"]


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    exists = db.scalar(select(User).where(User.email == data.email.lower()))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(
        email=data.email.lower(),
        hashed_password=hash_password(data.password),
        full_name=data.full_name.strip(),
        role=data.role,
        headline=data.headline.strip(),
        avatar_color=AVATAR_COLORS[abs(hash(data.email)) % len(AVATAR_COLORS)],
    )
    db.add(user)
    db.flush()
    db.add(Wallet(user_id=user.id, balance_cents=0))
    db.commit()
    db.refresh(user)
    token = create_access_token(str(user.id), {"role": user.role})
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=Token)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account suspended")
    token = create_access_token(str(user.id), {"role": user.role})
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
