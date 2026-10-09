"""Personal QORA schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.personal_qora.models import MEMORY_KINDS


class MemoryIn(BaseModel):
    kind: str = Field(pattern="^(" + "|".join(MEMORY_KINDS) + ")$")
    subject: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=2000)
    sensitivity: str = Field(default="private", pattern="^(public|private|sensitive)$")
    share_policy: str = Field(default="ask", pattern="^(deny|ask|allow)$")


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    subject: str
    content: str
    source: str
    confidence: float
    sensitivity: str
    share_policy: str
    user_editable: bool
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class GoalIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=2000)
    success_criteria: dict = Field(default_factory=dict)


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    status: str
    success_criteria: dict
    target_at: datetime | None
    created_at: datetime


class JourneyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    goal_id: int | None
    kind: str
    state: dict
    history: list
    updated_at: datetime
