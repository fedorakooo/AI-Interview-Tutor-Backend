from fastapi import APIRouter

from src.api.v1.endpoints.admin_ops import router as admin_ops_router
from src.api.v1.endpoints.auth import router as auth_router
from src.api.v1.endpoints.billing import router as billing_router
from src.api.v1.endpoints.current_user import router as current_user_router
from src.api.v1.endpoints.cv import router as cv_router
from src.api.v1.endpoints.growth import router as growth_router
from src.api.v1.endpoints.mfa import router as mfa_router
from src.api.v1.endpoints.notification_preferences import router as notification_preferences_router
from src.api.v1.endpoints.oauth import router as oauth_router
from src.api.v1.endpoints.orgs import router as orgs_router
from src.api.v1.endpoints.privacy import router as privacy_router
from src.api.v1.endpoints.user_management import router as user_management_router

router = APIRouter(prefix="/api/v1")

router.include_router(auth_router)
router.include_router(oauth_router)
router.include_router(mfa_router)
router.include_router(current_user_router)
router.include_router(notification_preferences_router)
router.include_router(cv_router)
router.include_router(user_management_router)
router.include_router(billing_router)
router.include_router(privacy_router)
router.include_router(admin_ops_router)
router.include_router(orgs_router)
router.include_router(growth_router)





