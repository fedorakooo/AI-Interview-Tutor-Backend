from __future__ import annotations

import contextvars
import uuid
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

CORRELATION_HEADER = "X-Correlation-ID"

_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Propagate or mint a correlation id for every HTTP request."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        incoming = request.headers.get(CORRELATION_HEADER) or request.headers.get(CORRELATION_HEADER.lower())
        correlation_id = incoming.strip() if incoming else str(uuid.uuid4())
        token = _correlation_id.set(correlation_id)
        try:
            response = await call_next(request)
        finally:
            _correlation_id.reset(token)
        response.headers[CORRELATION_HEADER] = correlation_id
        return response
