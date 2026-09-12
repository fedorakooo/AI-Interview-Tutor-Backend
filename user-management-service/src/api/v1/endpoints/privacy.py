"""GDPR data export (DSAR) endpoint."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from jwt_handler.value_objects import AccessTokenPayload

from src.api.dependencies.database import get_unit_of_work
from src.api.security import require_authenticated
from src.domain.interfaces.database.uow import IUnitOfWork

router = APIRouter(prefix="/privacy", tags=["Privacy"])


@router.get("/export")
async def export_my_data(
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
) -> dict:
    user_id = UUID(payload["id"])
    async with uow:
        user = await uow.user_repository.get_by_id(user_id)
        uploads = await uow.user_cv_upload_repository.list_by_user_id(user_id)

    if user is None:
        return {"detail": "User not found"}

    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "first_name": user.first_name,
            "second_name": user.second_name,
            "phone_number": user.phone_number,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "is_email_verified": user.is_email_verified,
            "subscription_tier": user.subscription_tier,
            "created_at": user.created_at.isoformat(),
            "modified_at": user.modified_at.isoformat(),
        },
        "cv_uploads": [
            {
                "id": str(upload.id),
                "correlation_id": str(upload.correlation_id),
                "status": upload.status.value if hasattr(upload.status, "value") else str(upload.status),
                "original_filename": upload.original_filename,
                "created_at": upload.created_at.isoformat() if upload.created_at else None,
            }
            for upload in uploads
        ],
        "note": (
            "Interview sessions, practice plans, and notifications live in MongoDB; "
            "request full package via support or the user_deleted cleanup pipeline."
        ),
    }
