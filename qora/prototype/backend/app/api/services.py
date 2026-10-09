"""Public catalog + provider service management."""
import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_roles
from app.db.base import get_db
from app.db.models import Category, Review, Service, User
from app.schemas.schemas import (
    CategoryOut,
    ReviewCreate,
    ReviewOut,
    ServiceCreate,
    ServiceOut,
    ServiceUpdate,
)

router = APIRouter(tags=["services"])


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "service"


def _service_query():
    return (
        select(Service)
        .options(joinedload(Service.category), joinedload(Service.provider))
        .where(Service.status == "active")
    )


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.scalars(select(Category).order_by(Category.name)).all()


@router.get("/services", response_model=list[ServiceOut])
def list_services(
    db: Session = Depends(get_db),
    search: str | None = Query(default=None, max_length=120),
    category: str | None = Query(default=None, max_length=80),
    sort: str = Query(default="newest", pattern="^(newest|price_asc|price_desc|rating)$"),
    limit: int = Query(default=24, ge=1, le=60),
):
    q = _service_query()
    if search:
        like = f"%{search.strip()}%"
        q = q.where(
            Service.title.ilike(like)
            | Service.description.ilike(like)
            | Service.tags.ilike(like)
        )
    if category:
        q = q.join(Service.category).where(Category.slug == category)
    order = {
        "newest": Service.created_at.desc(),
        "price_asc": Service.price_cents.asc(),
        "price_desc": Service.price_cents.desc(),
        "rating": Service.rating_avg.desc(),
    }[sort]
    return db.scalars(q.order_by(order).limit(limit)).all()


@router.get("/services/{service_id}", response_model=ServiceOut)
def get_service(service_id: int, db: Session = Depends(get_db)):
    service = db.scalar(_service_query().where(Service.id == service_id))
    if not service:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")
    return service


@router.get("/services/{service_id}/reviews", response_model=list[ReviewOut])
def service_reviews(service_id: int, db: Session = Depends(get_db)):
    q = (
        select(Review)
        .options(Review.author)
        .where(Review.service_id == service_id)
        .order_by(Review.created_at.desc())
    )
    return db.scalars(q).all()


@router.post("/services", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
def create_service(
    data: ServiceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("provider")),
):
    category = db.get(Category, data.category_id)
    if not category:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown category")
    slug = slugify(data.title)
    if db.scalar(select(Service).where(Service.slug == slug)):
        slug = f"{slug}-{user.id}"
    service = Service(
        **data.model_dump(),
        slug=slug,
        provider_id=user.id,
    )
    db.add(service)
    db.commit()
    return db.scalar(_service_query().where(Service.id == service.id))


@router.patch("/services/{service_id}", response_model=ServiceOut)
def update_service(
    service_id: int,
    data: ServiceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("provider", "admin")),
):
    service = db.get(Service, service_id)
    if not service:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")
    if service.provider_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your service")
    payload = data.model_dump(exclude_unset=True)
    if "category_id" in payload and not db.get(Category, payload["category_id"]):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown category")
    for k, v in payload.items():
        setattr(service, k, v)
    db.commit()
    return db.scalar(_service_query().where(Service.id == service.id))


@router.delete("/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(
    service_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("provider", "admin")),
):
    service = db.get(Service, service_id)
    if not service:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Service not found")
    if service.provider_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your service")
    if service.orders_count > 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Service has orders — pause it instead")
    db.delete(service)
    db.commit()


@router.post("/reviews", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def create_review(
    data: ReviewCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.db.models import Order  # local import to avoid cycle in docs

    order = db.get(Order, data.order_id)
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    if order.buyer_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the buyer can review")
    if order.status != "completed":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Review after the order is completed")
    if order.review:
        raise HTTPException(status.HTTP_409_CONFLICT, "Order already reviewed")

    review = Review(
        order_id=order.id,
        service_id=order.service_id,
        author_id=user.id,
        rating=data.rating,
        comment=data.comment.strip(),
    )
    db.add(review)
    db.flush()
    service = db.get(Service, order.service_id)
    stats = db.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(Review.service_id == service.id)
    ).one()
    service.rating_avg = round(float(stats[0] or 0), 2)
    service.rating_count = int(stats[1] or 0)
    db.commit()
    db.refresh(review)
    return review
