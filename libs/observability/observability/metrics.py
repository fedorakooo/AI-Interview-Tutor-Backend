from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

_lock = Lock()
_counters: dict[str, float] = defaultdict(float)
_histograms: dict[str, list[float]] = defaultdict(list)


def inc(name: str, value: float = 1.0, **labels: str) -> None:
    key = _format_key(name, labels)
    with _lock:
        _counters[key] += value


def observe(name: str, value: float, **labels: str) -> None:
    key = _format_key(name, labels)
    with _lock:
        bucket = _histograms[key]
        bucket.append(value)
        if len(bucket) > 5000:
            del bucket[:2500]


def _format_key(name: str, labels: dict[str, str]) -> str:
    if not labels:
        return name
    parts = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    return f"{name}{{{parts}}}"


def metrics_response() -> PlainTextResponse:
    lines: list[str] = []
    with _lock:
        for key, value in sorted(_counters.items()):
            lines.append(f"{key} {value}")
        for key, values in sorted(_histograms.items()):
            if not values:
                continue
            lines.append(f"{key}_count {len(values)}")
            lines.append(f"{key}_sum {sum(values)}")
            lines.append(f"{key}_avg {sum(values) / len(values)}")
    body = "\n".join(lines) + ("\n" if lines else "")
    return PlainTextResponse(body or "# no metrics yet\n", media_type="text/plain; version=0.0.4")


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record request counts and latency for Prometheus-style scraping."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in {"/metrics", "/health"}:
            return await call_next(request)
        started = time.perf_counter()
        status = "500"
        try:
            response = await call_next(request)
            status = str(response.status_code)
            return response
        finally:
            elapsed = time.perf_counter() - started
            route = request.url.path
            inc("http_requests_total", method=request.method, path=route, status=status)
            observe("http_request_duration_seconds", elapsed, method=request.method, path=route)
