"""Runtime router — model availability and admin-managed policy-gated tools."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.modules.runtime.gateway import ModelGateway
from app.modules.runtime.tools import ToolService
from app.modules.runtime import models as _models  # noqa: F401  (register tables for create_all)
from app.shared.deps import require_roles

router = APIRouter(prefix="/runtime", tags=["runtime"])


class ToolRegisterIn(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    description: str = Field(default="", max_length=255)
    input_schema: dict = Field(default_factory=dict)
    output_schema: dict = Field(default_factory=dict)
    auth_requirement: str = Field(default="none", max_length=40)
    risk_class: str = Field(default="LOW", pattern="^(LOW|MEDIUM|HIGH)$")
    allowed_services: list[int | str] = Field(default_factory=list)
    timeout_ms: int = Field(default=1000, ge=50, le=5000)
    enabled: bool = True


@router.get("/tools")
def tools(db: Session = Depends(get_db), admin=Depends(require_roles("admin"))):
    return {"items": ToolService.list_tools(db)}


@router.get("/tools/invocations")
def tool_invocations(
    limit: int = Query(default=50, ge=1, le=200),
    session_id: int | None = None,
    db: Session = Depends(get_db),
    admin=Depends(require_roles("admin")),
):
    return {"items": ToolService.invocation_log(db, limit, session_id)}


@router.post("/tools", status_code=201)
def register_tool(
    data: ToolRegisterIn,
    db: Session = Depends(get_db),
    admin=Depends(require_roles("admin")),
):
    row = ToolService.register(db, data.model_dump(), admin.id)
    return ToolService.serialize(row)


@router.get("/models")
def models(admin=Depends(require_roles("admin"))):
    adapter = ModelGateway.select({})
    return {
        "provider_in_use": adapter.name,
        "configured_provider": settings.MODEL_PROVIDER,
        "adapters": ["local", "openai_compatible"],
        "routing_signals": ["capability", "cost", "latency", "availability", "policy", "quality"],
    }
