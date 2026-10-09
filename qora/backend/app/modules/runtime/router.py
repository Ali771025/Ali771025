"""Runtime router — introspection of the model gateway (admin/dev)."""
from fastapi import APIRouter, Depends

from app.core.config import settings
from app.modules.runtime.gateway import ModelGateway
from app.modules.runtime import models as _models  # noqa: F401  (register tables for create_all)

router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.get("/models")
def models():
    adapter = ModelGateway.select({})
    return {
        "provider_in_use": adapter.name,
        "configured_provider": settings.MODEL_PROVIDER,
        "adapters": ["local", "openai_compatible"],
        "routing_signals": ["capability", "cost", "latency", "availability", "policy", "quality"],
    }
