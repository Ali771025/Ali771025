from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Role(StrEnum):
    FLIGHT_EXPERT = "FLIGHT_EXPERT"
    FLIGHT_MANAGER = "FLIGHT_MANAGER"


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ControlAction(StrEnum):
    ARM = "ARM"
    DISARM = "DISARM"
    TAKEOFF = "TAKEOFF"
    HOLD = "HOLD"
    RESUME_MISSION = "RESUME_MISSION"
    RETURN_TO_HOME = "RETURN_TO_HOME"
    LAND = "LAND"
    ABORT_MISSION = "ABORT_MISSION"


class Envelope(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    message_id: str = Field(min_length=8, max_length=128)
    topic: str = Field(min_length=2, max_length=64)
    source: str = Field(min_length=2, max_length=64)
    sequence_no: int = Field(ge=0)
    sent_at_ms: int = Field(gt=0)
    host_monotonic_ms: int | None = Field(default=None, ge=0)
    payload: dict[str, Any]
    crc32: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{8}$")
    hmac_sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    role: Role
    display_name: str


class UserView(BaseModel):
    username: str
    display_name: str
    role: Role


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(min_length=2, max_length=3000)


class AdvisoryAction(StrEnum):
    CONTINUE = "CONTINUE"
    REQUEST_SENSOR_UPDATE = "REQUEST_SENSOR_UPDATE"
    REQUEST_REPLAN = "REQUEST_REPLAN"
    HOLD = "HOLD"
    RETURN = "RETURN"
    LAND = "LAND"
    ABSTAIN = "ABSTAIN"


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    risk_level: Severity
    suggested_action: AdvisoryAction
    evidence_ids: list[str] = []
    model: str
    advisory_only: Literal[True] = True


class ControlIntentRequest(BaseModel):
    action: ControlAction
    reason: str = Field(min_length=5, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=128)


class ControlDecisionRequest(BaseModel):
    note: str = Field(default="", max_length=500)

