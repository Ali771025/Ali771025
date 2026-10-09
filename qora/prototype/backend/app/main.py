"""QORA API — FastAPI application entrypoint."""
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import admin, assistant, auth, orders, services, wallet
from app.api.deps import get_optional_user
from app.core.config import settings
from app.db.base import Base, engine, get_db
from app.db.models import Category, Order, Review, Service, User
from app.schemas.schemas import StatsOut

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Backend API for the QORA consumer AI service network — services, orders, wallet, reviews, admin.",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/api/stats", response_model=StatsOut, tags=["stats"])
def public_stats(db: Session = Depends(get_db), _user=Depends(get_optional_user)):
    gmv = (
        db.scalar(select(func.coalesce(func.sum(Order.price_cents), 0)).where(Order.status.in_(["delivered", "completed"])))
        or 0
    )
    return StatsOut(
        services=db.scalar(select(func.count(Service.id))) or 0,
        providers=db.scalar(select(func.count(User.id)).where(User.role == "provider")) or 0,
        consumers=db.scalar(select(func.count(User.id)).where(User.role == "consumer")) or 0,
        orders=db.scalar(select(func.count(Order.id))) or 0,
        completed_orders=db.scalar(select(func.count(Order.id)).where(Order.status == "completed")) or 0,
        gmv_cents=int(gmv),
        categories=db.scalar(select(func.count(Category.id))) or 0,
        avg_rating=round(float(db.scalar(select(func.avg(Review.rating))) or 0), 2),
    )


app.include_router(auth.router, prefix="/api")
app.include_router(services.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(wallet.router, prefix="/api")
app.include_router(assistant.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
