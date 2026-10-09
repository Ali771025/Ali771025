"""Admin endpoints: platform stats, user management, order oversight."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_roles
from app.db.base import get_db
from app.db.models import Category, Order, Review, Service, User
from app.schemas.schemas import AdminUserUpdate, OrderOut, StatsOut, UserOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db), _admin: User = Depends(require_roles("admin"))):
    services = db.scalar(select(func.count(Service.id))) or 0
    providers = db.scalar(select(func.count(User.id)).where(User.role == "provider")) or 0
    consumers = db.scalar(select(func.count(User.id)).where(User.role == "consumer")) or 0
    orders = db.scalar(select(func.count(Order.id))) or 0
    completed = db.scalar(select(func.count(Order.id)).where(Order.status == "completed")) or 0
    gmv = db.scalar(select(func.coalesce(func.sum(Order.price_cents), 0)).where(Order.status.in_(["delivered", "completed"]))) or 0
    categories = db.scalar(select(func.count(Category.id))) or 0
    avg_rating = db.scalar(select(func.avg(Review.rating))) or 0
    return StatsOut(
        services=services,
        providers=providers,
        consumers=consumers,
        orders=orders,
        completed_orders=completed,
        gmv_cents=int(gmv),
        categories=categories,
        avg_rating=round(float(avg_rating), 2),
    )


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _admin: User = Depends(require_roles("admin"))):
    return db.scalars(select(User).order_by(User.created_at.desc())).all()


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    data: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == admin.id and not data.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot suspend yourself")
    user.is_active = data.is_active
    db.commit()
    db.refresh(user)
    return user


@router.get("/orders", response_model=list[OrderOut])
def all_orders(db: Session = Depends(get_db), _admin: User = Depends(require_roles("admin"))):
    q = (
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
    return db.scalars(q).unique().all()
