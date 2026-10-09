"""Identity schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)
    display_name: str = Field(min_length=2, max_length=120)
    roles_wanted: list[str] = Field(default=["consumer"])  # consumer | creator [PRD]


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    device_platform: str = Field(default="web", pattern="^(web|ios|android)$")


class RefreshIn(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    roles: str
    account_status: str
    auth_provider: str
    created_at: datetime


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int | None
    ip: str | None
    user_agent: str | None
    expires_at: datetime
    created_at: datetime
