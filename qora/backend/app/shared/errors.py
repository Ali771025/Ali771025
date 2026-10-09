"""Canonical error envelope (API_CONTRACT §0)."""
from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details=None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []
        super().__init__(message)


def _envelope(code: str, message: str, details, trace_id: str) -> dict:
    return {"error": {"code": code, "message": message, "details": details, "trace_id": trace_id}}


# Canonical codes [API_CONTRACT §0]
VALIDATION_ERROR = "VALIDATION_ERROR"
UNAUTHENTICATED = "UNAUTHENTICATED"
FORBIDDEN = "FORBIDDEN"
NOT_FOUND = "NOT_FOUND"
CONFLICT = "CONFLICT"
RATE_LIMITED = "RATE_LIMITED"
MODEL_FAILURE = "MODEL_FAILURE"
TOOL_FAILURE = "TOOL_FAILURE"
MISSING_CONTEXT = "MISSING_CONTEXT"
PERMISSION_DENIED = "PERMISSION_DENIED"
KNOWLEDGE_FAILURE = "KNOWLEDGE_FAILURE"
SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
POLICY_BLOCK = "POLICY_BLOCK"
TIMEOUT = "TIMEOUT"
LOW_CONFIDENCE = "LOW_CONFIDENCE"


def install_error_handlers(app):
    from app.shared.logging import get_trace_id

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details, get_trace_id()),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=_envelope("INTERNAL_ERROR", "Unexpected server error", [], get_trace_id()),
        )
