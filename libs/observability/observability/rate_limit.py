from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class InMemoryRateLimiter:
    """Simple sliding-window rate limiter (per-process; use Redis in multi-instance prod)."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            cutoff = now - self.window_seconds
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                return False
            bucket.append(now)
            return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        max_requests: int = 120,
        window_seconds: float = 60.0,
        path_prefixes: tuple[str, ...] = ("/api/",),
    ) -> None:
        super().__init__(app)
        self.limiter = InMemoryRateLimiter(max_requests=max_requests, window_seconds=window_seconds)
        self.path_prefixes = path_prefixes

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if not any(path.startswith(prefix) for prefix in self.path_prefixes):
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        key = f"{client}:{path.split('/')[3] if path.count('/') >= 3 else path}"
        if not self.limiter.allow(key):
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
        return await call_next(request)
