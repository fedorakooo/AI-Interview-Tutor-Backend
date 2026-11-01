"""Private API consumed by trusted backend services, never by browsers."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from shared_models.assessment.contracts import AssessmentContext
from shared_models.feature_flags.flags import feature_enabled

from src.api.dependencies.database import get_unit_of_work
from src.api.dependencies.internal import require_internal_service
from src.application.use_cases.assessments import AssessmentFlowError, GetAssessmentContextUseCase
from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.interfaces.database.uow import IUnitOfWork

router = APIRouter(
    prefix="/api/internal/assessment-attempts",
    tags=["Internal assessment"],
    dependencies=[Depends(require_internal_service)],
)


@router.get("/{attempt_id}/context", response_model=AssessmentContext)
async def get_assessment_context(
    attempt_id: UUID,
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
) -> AssessmentContext:
    if not feature_enabled("EMPLOYER_ASSESSMENT_DEMO", False):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        return await GetAssessmentContextUseCase(uow)(attempt_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment attempt not found") from exc
    except AssessmentFlowError as exc:
        # Do not disclose which prerequisite (CV, vacancy, or state) failed.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Assessment is not ready") from exc
