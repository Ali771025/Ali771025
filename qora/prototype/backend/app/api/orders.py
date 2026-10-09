"""Order lifecycle: purchase, accept, deliver, complete, cancel, refund."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.base import get_db
from app.db.models import Order, Service, Transaction, User, Wallet
from app.schemas.schemas import OrderCreate, OrderOut, StatusUpdate

router = APIRouter(prefix="/orders", tags=["orders"])


def _order_query():
    return (
        select(Order)
        .options(
            joinedload(Order.service).joinedload(Service.category),
            joinedload(Order.service).joinedload(Service.provider),
            joinedload(Order.buyer),
            joinedload(Order.provider),
            joinedload(Order.review),
        )
        .order_by(Order.created_at.desc())
    )


def _get_wallet(db: Session, user_id: int) -> Wallet:
    wallet = db.scalar(select(Wallet).where(Wallet.user_id == user_id))
    if not wallet:
        wallet = Wallet(user_id=user_id, balance_cents=0)
        db.add(wallet)
        db.flush()
    return wallet


@router.get("", response_model=list[OrderOut])
def my_orders(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    role: str = "all",  # all | buyer | provider
):
    q = _order_query()
    if role == "buyer":
        q = q.where(Order.buyer_id == user.id)
    elif role == "provider":
        q = q.where(Order.provider_id == user.id)
    else:
        q = q.where((Order.buyer_id == user.id) | (Order.provider_id == user.id))
    return db.scalars(q).unique().all()


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    data: OrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service = db.get(Service, data.service_id)
    if not service or service.status != "active":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not available")
    if service.provider_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot order your own service")

    wallet = _get_wallet(db, user.id)
    if wallet.balance_cents < service.price_cents:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "Insufficient wallet balance — top up first")

    order = Order(
        service_id=service.id,
        buyer_id=user.id,
        provider_id=service.provider_id,
        requirements=data.requirements.strip(),
        price_cents=service.price_cents,
        status="pending",
    )
    db.add(order)
    wallet.balance_cents -= service.price_cents
    db.add(
        Transaction(
            wallet_id=wallet.id,
            kind="purchase",
            amount_cents=-service.price_cents,
            description=f"Order #{service.id} — {service.title}",
        )
    )
    service.orders_count += 1
    db.commit()
    return db.scalar(_order_query().where(Order.id == order.id))


def _load_owned_order(db: Session, order_id: int, user: User) -> Order:
    order = db.scalar(_order_query().where(Order.id == order_id))
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    if order.buyer_id != user.id and order.provider_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your order")
    return order


@router.patch("/{order_id}/status", response_model=OrderOut)
def update_status(
    order_id: int,
    data: StatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = _load_owned_order(db, order_id, user)
    buyer_side = order.buyer_id == user.id
    current, target = order.status, data.status

    allowed = {
        ("pending", "in_progress"): "provider",
        ("pending", "cancelled"): "both",
        ("in_progress", "delivered"): "provider",
        ("in_progress", "cancelled"): "provider",
        ("delivered", "completed"): "buyer",
    }
    owner = allowed.get((current, target))
    if owner is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Cannot move order from '{current}' to '{target}'")
    if owner == "provider" and buyer_side:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the provider can do this")
    if owner == "buyer" and not buyer_side:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the buyer can do this")

    order.status = target
    now = datetime.now(timezone.utc)
    order.updated_at = now

    buyer_wallet = _get_wallet(db, order.buyer_id)
    provider_wallet = _get_wallet(db, order.provider_id)

    if target == "delivered":
        order.delivered_at = now
    elif target == "cancelled":
        # Refund buyer in full (also reverses purchase)
        buyer_wallet.balance_cents += order.price_cents
        db.add(
            Transaction(
                wallet_id=buyer_wallet.id,
                kind="refund",
                amount_cents=order.price_cents,
                description=f"Refund — order #{order.id} cancelled",
            )
        )
    elif target == "completed":
        # Release payment to provider minus platform fee
        fee = order.price_cents * settings.PLATFORM_FEE_PERCENT // 100
        earnings = order.price_cents - fee
        provider_wallet.balance_cents += earnings
        db.add(
            Transaction(
                wallet_id=provider_wallet.id,
                kind="earning",
                amount_cents=earnings,
                description=f"Earnings — order #{order.id} (fee {settings.PLATFORM_FEE_PERCENT}%)",
            )
        )

    db.commit()
    return db.scalar(_order_query().where(Order.id == order.id))


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _load_owned_order(db, order_id, user)
