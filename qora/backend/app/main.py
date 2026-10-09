"""QORA Platform — Modular Monolith entrypoint [TECH] (ARCHITECTURE §2).

All domain routers live under /api/v1. The error envelope is canonical (API_CONTRACT §0).
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import Base, engine
from app.modules import ROUTERS
from app.shared.errors import install_error_handlers
from app.shared.logging import get_trace_id, log, set_trace_id

# Import every module's models so create_all sees them (via modules package).
import app.modules  # noqa: F401

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description=(
        "QORA — Consumer AI Platform + Personal AI + AI Service Network. "
        "Phase 0/1: identity, profiles, personal QORA, permissions, intent engine, "
        "service registry, runtime, conversations, outcomes, rewards."
    ),
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    tid = request.headers.get("x-trace-id") or ("trc_" + __import__("uuid").uuid4().hex[:16])
    set_trace_id(tid)
    response = await call_next(request)
    response.headers["x-trace-id"] = get_trace_id()
    return response


install_error_handlers(app)

for r in ROUTERS:
    app.include_router(r, prefix="/api/v1")


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "phase": "0+1", "trace_id": get_trace_id()}


@app.get("/api/v1/_modules")
def modules():
    log("platform").info("modules listing")
    from app.modules import ROUTERS as _r

    return {
        "modules": sorted({getattr(r, "module_name", None) or r.prefix.strip("/").split("/")[0] for r in _r} - {None, ""}),
        "boundary_rule": "modules communicate via service interfaces only",
    }
