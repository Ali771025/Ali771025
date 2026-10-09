"""QORA Platform — modular monolith entrypoint [TECH] (ARCHITECTURE §2)."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import Base, SessionLocal, engine
from app.modules import ROUTERS
from app.shared.errors import install_error_handlers
from app.shared.logging import get_trace_id, log, set_trace_id

# Every model module (including the shared audit log) is imported before create_all.
import app.modules  # noqa: F401

Base.metadata.create_all(bind=engine)

# Built-in tool handlers are reviewed platform code, never user-supplied code.
from app.modules.runtime.tools import ToolService

with SessionLocal() as _bootstrap_db:
    ToolService.ensure_builtins(_bootstrap_db)

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description=(
        "QORA — Consumer AI Platform + Personal AI + AI Service Network. "
        "Phases 0–4: identity, creator platform, orchestration, trust, reliability, analytics, and insights."
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

for api_router in ROUTERS:
    app.include_router(api_router, prefix="/api/v1")


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "phase": "3+4", "trace_id": get_trace_id()}


@app.get("/api/v1/_modules")
def modules():
    log("platform").info("modules listing")
    from app.modules import ROUTERS as registered_routers

    return {
        "modules": sorted({
            tag
            for api_router in registered_routers
            for tag in (api_router.tags or [])
        }),
        "boundary_rule": "modules communicate via service interfaces only",
        "delivery": "Phase 3 multi-service orchestration, trust/reliability; Phase 4 daily analytics and insights",
    }
