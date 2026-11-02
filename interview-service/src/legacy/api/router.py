from fastapi import APIRouter

from src.legacy.api.endpoints.coding import router as coding_router
from src.legacy.api.endpoints.cv import router as cv_router
from src.legacy.api.endpoints.interview import router as interview_router
from src.legacy.api.endpoints.jd import router as jd_router
from src.legacy.api.endpoints.sample import router as sample_router
from src.legacy.api.endpoints.sessions import router as sessions_router

router = APIRouter(prefix="/api/v1")

router.include_router(interview_router)
router.include_router(sessions_router)
router.include_router(cv_router)
router.include_router(coding_router)
router.include_router(jd_router)
router.include_router(sample_router)
