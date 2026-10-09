"""SQLAlchemy ORM models for the QORA marketplace."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), default="consumer")  # consumer | provider | admin
    headline: Mapped[str] = mapped_column(String(200), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    avatar_color: Mapped[str] = mapped_column(String(20), default="#6366f1")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    services: Mapped[list["Service"]] = relationship(back_populates="provider", cascade="all, delete-orphan")
    wallet: Mapped["Wallet"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    icon: Mapped[str] = mapped_column(String(40), default="sparkles")  # lucide icon name
    description: Mapped[str] = mapped_column(String(255), default="")

    services: Mapped[list["Service"]] = relationship(back_populates="category")


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text)
    price_cents: Mapped[int] = mapped_column(Integer)
    delivery_days: Mapped[int] = mapped_column(Integer, default=7)
    tags: Mapped[str] = mapped_column(Text, default="")  # comma separated
    status: Mapped[str] = mapped_column(String(20), default="active")  # draft | active | paused
    rating_avg: Mapped[float] = mapped_column(Float, default=0.0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    orders_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    provider_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    category: Mapped["Category"] = relationship(back_populates="services")
    provider: Mapped["User"] = relationship(back_populates="services")
    orders: Mapped[list["Order"]] = relationship(back_populates="service")
    reviews: Mapped[list["Review"]] = relationship(back_populates="service", cascade="all, delete-orphan")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    requirements: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # pending | in_progress | delivered | completed | cancelled
    price_cents: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    provider_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    service: Mapped["Service"] = relationship(back_populates="orders")
    buyer: Mapped["User"] = relationship(foreign_keys=[buyer_id])
    provider: Mapped["User"] = relationship(foreign_keys=[provider_id])
    review: Mapped["Review | None"] = relationship(back_populates="order", uselist=False)


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rating: Mapped[int] = mapped_column(Integer)  # 1..5
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), unique=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    order: Mapped["Order"] = relationship(back_populates="review")
    service: Mapped["Service"] = relationship(back_populates="reviews")
    author: Mapped["User"] = relationship()


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    balance_cents: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="wallet")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="wallet", cascade="all, delete-orphan")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # topup | purchase | earning | refund | payout
    kind: Mapped[str] = mapped_column(String(20))
    amount_cents: Mapped[int] = mapped_column(Integer)  # positive = credit, negative = debit
    description: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    wallet_id: Mapped[int] = mapped_column(ForeignKey("wallets.id"))
    wallet: Mapped["Wallet"] = relationship(back_populates="transactions")
