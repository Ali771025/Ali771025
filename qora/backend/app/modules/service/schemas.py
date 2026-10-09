"""Service schemas — API_CONTRACT §6."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ServiceCreate(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    summary: str = Field(default="", max_length=255)
    description: str = Field(default="", max_length=4000)
    purpose: str = Field(default="", max_length=2000)
    audience: str = Field(default="", max_length=255)
    category: str = Field(default="general", max_length=60)
    risk_level: str = Field(default="LOW", pattern="^(LOW|MEDIUM|HIGH|RESTRICTED)$")
    intent_slugs: list[str] = Field(default_factory=list)
    capability_slugs: list[str] = Field(default_factory=list)


class VersionCreate(BaseModel):
    purpose: str = ""
    method: str = ""
    behavior: str = ""
    system_instructions: str = ""
    boundaries: str = ""
    outcome_definition: dict = Field(default_factory=dict)
    model_requirements: dict = Field(default_factory=dict)
    context_requirements: list[str] = Field(default_factory=list)
    knowledge_config: dict = Field(default_factory=dict)
    tools_config: dict = Field(default_factory=dict)
    examples: list = Field(default_factory=list)


class VersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service_id: int
    version_no: int
    purpose: str
    method: str
    behavior: str
    system_instructions: str
    boundaries: str
    outcome_definition: dict
    model_requirements: dict
    context_requirements: list
    knowledge_config: dict
    tools_config: dict
    examples: list
    created_at: datetime


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    summary: str
    description: str
    purpose: str
    audience: str
    category: str
    risk_level: str
    visibility: str
    lifecycle_status: str
    verification_status: str
    current_version_id: int | None
    published_at: datetime | None
    created_at: datetime


class DiscoveryItem(BaseModel):
    service: ServiceOut
    creator: dict
    outcome: dict
    trust: dict
    rank: dict
    followed: bool


class LifecycleAction(BaseModel):
    action: str = Field(pattern="^(submit_test|request_qualification|publish|pause|unlist|rollback|improve)$")
    reason: str = ""
