"""Conversation schemas — response shape follows API_CONTRACT §4 (implemented subset)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    content_type: str = Field(default="text", pattern="^text$")


class RecoveryIn(BaseModel):
    option: str = Field(pattern="^(continue_with_qora|try_another_service|retry|stop)$")


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    content_blocks: dict
    created_at: datetime


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    active_service_id: int | None
    active_journey_id: int | None
    recovery_state: str
    created_at: datetime
    updated_at: datetime
