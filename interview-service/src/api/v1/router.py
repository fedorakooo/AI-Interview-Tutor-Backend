from fastapi import APIRouter

from src.api.v1.endpoints.interview import router as interview_router

router = APIRouter(prefix="/api/v1")

router.include_router(interview_router)
