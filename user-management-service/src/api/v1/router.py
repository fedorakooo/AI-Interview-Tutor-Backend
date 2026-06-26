from fastapi import APIRouter

from src.api.v1.endpoints.auth import router as auth_router
from src.api.v1.endpoints.current_user import router as current_user_router
from src.api.v1.endpoints.user_management import router as user_management_router

router = APIRouter(prefix="/api/v1")

router.include_router(auth_router)
router.include_router(current_user_router)
router.include_router(user_management_router)
