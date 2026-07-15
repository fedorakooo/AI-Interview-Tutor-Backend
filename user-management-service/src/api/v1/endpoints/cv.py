from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from jwt_handler.value_objects import AccessTokenPayload

from src.api.dependencies.use_cases.cv import get_cv_status_use_case, get_upload_cv_use_case
from src.api.security import require_authenticated
from src.api.v1.models.cv import CVStatusResponse, CVUploadAcceptedResponse
from src.application.use_cases.cv.get_cv_status_use_case import GetCVStatusUseCase
from src.application.use_cases.cv.upload_cv_use_case import UploadCVUseCase

router = APIRouter(prefix="/user/me/cv", tags=["CV"])


@router.post(
    "/",
    response_model=CVUploadAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid or empty PDF"},
        status.HTTP_413_CONTENT_TOO_LARGE: {"description": "File too large"},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"description": "Only PDF uploads are supported"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "S3 or RabbitMQ failure"},
    },
)
async def upload_cv(
    access_token: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    upload_cv_use_case: Annotated[UploadCVUseCase, Depends(get_upload_cv_use_case)],
    file: UploadFile = File(...),
) -> CVUploadAcceptedResponse:
    file_bytes = await file.read()
    upload = await upload_cv_use_case(
        user_id=UUID(access_token["id"]),
        file_bytes=file_bytes,
        filename=file.filename or "resume.pdf",
        content_type=file.content_type or "application/pdf",
    )
    return CVUploadAcceptedResponse(
        correlation_id=upload.correlation_id,
        status=upload.status.value,
    )


@router.get(
    "/status",
    response_model=CVStatusResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "No CV upload found"},
    },
)
async def get_cv_status(
    access_token: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    get_status_use_case: Annotated[GetCVStatusUseCase, Depends(get_cv_status_use_case)],
    correlation_id: UUID | None = None,
) -> CVStatusResponse:
    upload = await get_status_use_case(
        user_id=UUID(access_token["id"]),
        correlation_id=correlation_id,
    )
    return CVStatusResponse.from_entity(upload)
