from fastapi import APIRouter

from src.api.internal.erasure import router as erasure_router
from src.api.internal.feedback import router as feedback_router
from src.api.internal.reports import router as reports_router
from src.api.internal.spec_drafts import router as spec_drafts_router

router = APIRouter()

router.include_router(reports_router)
router.include_router(feedback_router)
router.include_router(spec_drafts_router)
router.include_router(erasure_router)
