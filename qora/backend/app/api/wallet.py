"""Wallet: balance, top-up (mock payment), transaction history."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.base import get_db
from app.db.models import Transaction, User, Wallet
from app.schemas.schemas import TopUpIn, WalletOut

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("", response_model=WalletOut)
def get_wallet(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    wallet = db.scalar(select(Wallet).where(Wallet.user_id == user.id))
    if not wallet:
        wallet = Wallet(user_id=user.id, balance_cents=0)
        db.add(wallet)
        db.commit()
        db.refresh(wallet)
    txs = db.scalars(
        select(Transaction).where(Transaction.wallet_id == wallet.id).order_by(Transaction.created_at.desc())
    ).all()
    return WalletOut(balance_cents=wallet.balance_cents, transactions=txs)


@router.post("/topup", response_model=WalletOut)
def top_up(data: TopUpIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    wallet = db.scalar(select(Wallet).where(Wallet.user_id == user.id))
    if not wallet:
        wallet = Wallet(user_id=user.id, balance_cents=0)
        db.add(wallet)
        db.flush()
    wallet.balance_cents += data.amount_cents
    db.add(
        Transaction(
            wallet_id=wallet.id,
            kind="topup",
            amount_cents=data.amount_cents,
            description="Wallet top-up (test payment)",
        )
    )
    db.commit()
    db.refresh(wallet)
    if len(wallet.transactions) > 50:
        pass  # history is paginated by recency on the client
    txs = db.scalars(
        select(Transaction).where(Transaction.wallet_id == wallet.id).order_by(Transaction.created_at.desc())
    ).all()
    return WalletOut(balance_cents=wallet.balance_cents, transactions=txs)
