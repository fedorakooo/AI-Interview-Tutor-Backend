from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.exception_handler import exception_container
from src.api.internal.erasure import router as erasure_router
from src.api.internal.feedback import router as feedback_router
from src.api.internal.reports import router as reports_router
from src.api.internal.spec_drafts import router as spec_drafts_router
from src.api.interview.endpoints import router as interview_router
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

app.include_router(interview_router)
app.include_router(reports_router)
app.include_router(feedback_router)
app.include_router(erasure_router)
app.include_router(spec_drafts_router)

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
