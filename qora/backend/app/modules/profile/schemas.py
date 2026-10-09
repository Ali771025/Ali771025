"""Profile schemas — note the deliberate split between private and public shapes."""
from pydantic import BaseModel, ConfigDict, Field


class PrivateProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    display_name: str
    language: str
    timezone: str
    preferences: dict


class PrivateProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=120)
    language: str | None = None
    timezone: str | None = None
    preferences: dict | None = None


class CreatorProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    display_name: str
    bio: str
    headline: str
    expertise_tags: list
    verification_status: str


class CreatorProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=120)
    bio: str | None = Field(default=None, max_length=2000)
    headline: str | None = Field(default=None, max_length=200)
    expertise_tags: list | None = None


class CreatorPublic(BaseModel):
    """Public projection — the ONLY shape allowed on public endpoints [PRD]."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    bio: str
    headline: str
    expertise_tags: list
    verification_status: str
    trust_score: float
