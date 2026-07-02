from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.exception_handler import exception_container
from src.api.v1.router import router
from src.config import settings

app = FastAPI(
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

app.mount("/static", StaticFiles(directory="src/static"), name="static")


@app.get("/")
async def root():
    return {
        "endpoints": {
            "interview_client": "/static/interview_client.html",
        }
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
