from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.exception_handler import exception_container
from src.api.internal.router import router as internal_router
from src.api.v1.router import router
from src.app.lifespan import lifespan
from src.config import settings

app = FastAPI(
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(internal_router)

exception_container(app)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def readiness(request: Request) -> JSONResponse:
    checks: dict[str, str] = {}
    try:
        checks["redis"] = "ok" if await request.app.state.redis_client.ping() else "unavailable"
    except Exception as exc:
        checks["redis"] = str(exc)

    try:
        await request.app.state.mongo_client.admin.command("ping")
        checks["mongodb"] = "ok"
    except Exception as exc:
        checks["mongodb"] = str(exc)

    if all(value == "ok" for value in checks.values()):
        return JSONResponse(content={"status": "ready", "checks": checks})

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "not_ready", "checks": checks},
    )
