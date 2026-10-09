"""Permission schemas — API_CONTRACT §3/§10."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GrantIn(BaseModel):
    service_id: int
    context_type: str = Field(pattern="^(career|goals|preferences|travel|language)$")
    scope: str = Field(default="*", max_length=255)
    mode: str = Field(pattern="^(ALLOW_ONCE|ALWAYS_ALLOW|DENY)$")
    expires_at: datetime | None = None


class GrantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service_id: int
    context_type: str
    scope: str
    mode: str
    consumed_at: datetime | None
    granted_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None


class PermissionNeed(BaseModel):
    """Returned in chat responses when a service needs context it cannot access."""

    context_type: str
    mode_options: list[str] = ["ALLOW_ONCE", "ALWAYS_ALLOW", "DENY"]
    suggested_grant: GrantIn | None = None
