from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from jwt_handler.value_objects import AccessTokenPayload
from pydantic import BaseModel
from shared_models.cv.cv_data import CVData

from src.api.dependencies.mongo import get_cv_analysis_repository
from src.api.security import require_authenticated
from src.domain.exceptions.cv_not_ready_error import CVNotReadyError
from src.domain.interfaces.mongo import IMongoRepository
from src.services.cv_data_resolver import CVDataResolver

router = APIRouter(prefix="/interview", tags=["CV"])


class LatestCVResponse(BaseModel):
    correlation_id: str | None
    source: str
    cv: CVData


@router.get(
    "/cv/latest",
    response_model=LatestCVResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "No completed CV analysis found"},
    },
)
async def get_latest_cv(
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    mongo_repository: Annotated[IMongoRepository, Depends(get_cv_analysis_repository)],
) -> LatestCVResponse:
    resolver = CVDataResolver(mongo_repository)
    try:
        result = await resolver.get_latest_completed(payload["id"])
    except CVNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No completed CV analysis found for the current user",
        ) from exc
    return LatestCVResponse(
        correlation_id=result.correlation_id,
        source=result.source,
        cv=result.cv_data,
    )
