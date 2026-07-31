from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach request/correlation/idempotency identifiers to every response.

    Sensitive mutation endpoints should receive an Idempotency-Key from the client. This middleware
    does not implement replay protection by itself; it guarantees traceability and prepares the
    contract for the idempotency store.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        correlation_id = request.headers.get("x-correlation-id") or request_id
        idempotency_key = request.headers.get("idempotency-key")

        request.state.request_id = request_id
        request.state.correlation_id = correlation_id
        request.state.idempotency_key = idempotency_key

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Correlation-ID"] = correlation_id
        if idempotency_key:
            response.headers["Idempotency-Key"] = idempotency_key
        return response
