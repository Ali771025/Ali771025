"""Pydantic request/response schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------- Auth / Users ----------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)
    full_name: str = Field(min_length=2, max_length=120)
    role: str = Field(default="consumer", pattern="^(consumer|provider)$")
    headline: str = Field(default="", max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: str
    headline: str
    bio: str
    avatar_color: str
    is_active: bool
    created_at: datetime


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    role: str
    headline: str
    avatar_color: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Categories ----------
class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    icon: str
    description: str


# ---------- Services ----------
class ServiceCreate(BaseModel):
    title: str = Field(min_length=4, max_length=160)
    description: str = Field(min_length=10)
    price_cents: int = Field(gt=0, le=10_000_000)
    delivery_days: int = Field(ge=1, le=90)
    category_id: int
    tags: str = Field(default="", max_length=255)
    status: str = Field(default="active", pattern="^(draft|active|paused)$")


class ServiceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=4, max_length=160)
    description: str | None = Field(default=None, min_length=10)
    price_cents: int | None = Field(default=None, gt=0, le=10_000_000)
    delivery_days: int | None = Field(default=None, ge=1, le=90)
    category_id: int | None = None
    tags: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, pattern="^(draft|active|paused)$")


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    description: str
    price_cents: int
    delivery_days: int
    tags: str
    status: str
    rating_avg: float
    rating_count: int
    orders_count: int
    created_at: datetime
    category: CategoryOut
    provider: UserPublic


# ---------- Orders ----------
class OrderCreate(BaseModel):
    service_id: int
    requirements: str = Field(default="", max_length=4000)


class StatusUpdate(BaseModel):
    status: str = Field(pattern="^(pending|in_progress|delivered|completed|cancelled)$")


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rating: int
    comment: str
    created_at: datetime
    author: UserPublic


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    requirements: str
    status: str
    price_cents: int
    created_at: datetime
    updated_at: datetime
    delivered_at: datetime | None
    service_id: int
    buyer_id: int
    provider_id: int
    service: ServiceOut
    buyer: UserPublic
    provider: UserPublic
    review: ReviewOut | None = None


# ---------- Reviews ----------
class ReviewCreate(BaseModel):
    order_id: int
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=2000)


# ---------- Wallet ----------
class TopUpIn(BaseModel):
    amount_cents: int = Field(gt=0, le=10_000_000)


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    amount_cents: int
    description: str
    created_at: datetime


class WalletOut(BaseModel):
    balance_cents: int
    transactions: list[TransactionOut]


# ---------- Assistant ----------
class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ServiceBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    price_cents: int
    rating_avg: float
    delivery_days: int
    category_name: str = ""


class ChatOut(BaseModel):
    reply: str
    suggestions: list[ServiceBrief] = []


# ---------- Admin / Stats ----------
class StatsOut(BaseModel):
    services: int
    providers: int
    consumers: int
    orders: int
    completed_orders: int
    gmv_cents: int
    categories: int
    avg_rating: float


class AdminUserUpdate(BaseModel):
    is_active: bool
