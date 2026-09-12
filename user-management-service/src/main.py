from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.exception_handler import exception_container
from src.api.v1.router import router
from src.config import settings
from src.lifespan import lifespan

app = FastAPI(
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

try:
    from observability import (
        CorrelationIdMiddleware,
        MetricsMiddleware,
        OpenTelemetryMiddleware,
        RateLimitMiddleware,
        init_langfuse,
        init_otel,
        init_sentry,
        metrics_response,
    )

    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(OpenTelemetryMiddleware)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RateLimitMiddleware, max_requests=180, window_seconds=60.0)
    init_sentry("user-management-service")
    init_langfuse()
    init_otel("user-management-service")
    HAS_OBSERVABILITY = True
except ImportError:  # pragma: no cover - optional local path dep
    HAS_OBSERVABILITY = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

exception_container(app)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


if HAS_OBSERVABILITY:

    @app.get("/metrics")
    async def metrics():
        return metrics_response()
