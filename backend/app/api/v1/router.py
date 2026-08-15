from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    advanced_operations,
    auth,
    connector,
    meta,
    notifications,
    owner,
    report,
    software,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(owner.router)
api_router.include_router(software.router)
api_router.include_router(report.router)
api_router.include_router(connector.router)
api_router.include_router(notifications.router)
api_router.include_router(meta.router)
api_router.include_router(advanced_operations.router)
