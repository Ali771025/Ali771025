from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.application.common.exceptions import (
    ApplicationError,
    BusinessRuleViolation,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)

ERROR_STATUS = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    BusinessRuleViolation: 422,
    ForbiddenError: status.HTTP_403_FORBIDDEN,
}


def register_application_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApplicationError)
    async def application_error_handler(request: Request, exc: ApplicationError) -> JSONResponse:
        http_status = ERROR_STATUS.get(type(exc), status.HTTP_400_BAD_REQUEST)
        return JSONResponse(
            status_code=http_status,
            content={"code": exc.code, "message": exc.message, "details": exc.details},
        )
