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
