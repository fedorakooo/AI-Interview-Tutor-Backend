from fastapi import APIRouter
from src.api.v1.endpoints.attempts import router as attempts_router
from src.api.v1.endpoints.plans import router as plans_router
from src.api.v1.endpoints.profile import router as profile_router

router = APIRouter(prefix="/api/v1")

router.include_router(profile_router)
router.include_router(plans_router)
router.include_router(attempts_router)
