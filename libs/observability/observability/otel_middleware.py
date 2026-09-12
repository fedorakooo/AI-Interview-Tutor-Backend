"""OpenTelemetry middleware stub — sets span attributes from correlation id."""

from __future__ import annotations

from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from observability.correlation import get_correlation_id


class OpenTelemetryMiddleware(BaseHTTPMiddleware):
    """Attach correlation id to the active span when OTel is available."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        span = _current_span()
        if span is not None:
            correlation_id = get_correlation_id()
            if correlation_id:
                span.set_attribute("correlation.id", correlation_id)
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.route", request.url.path)
        response = await call_next(request)
        if span is not None:
            span.set_attribute("http.status_code", response.status_code)
        return response


def _current_span():
    try:
        from opentelemetry import trace

        return trace.get_current_span()
    except Exception:
        return None
