from uuid import UUID

from fastapi import APIRouter, Depends
from shared_models.assessment import AssessmentOverview, FocusDetail, ReviewRequest

from src.api.dependencies.container import ContainerDep
from src.api.security import require_internal_service

router = APIRouter(
    prefix="/api/internal/reports",
    tags=["Internal reports"],
    dependencies=[Depends(require_internal_service)],
)


@router.get("/{attempt_id}", response_model=AssessmentOverview)
async def get_overview(attempt_id: UUID, container: ContainerDep) -> AssessmentOverview:
    return await container.get_assessment_overview_use_case(attempt_id)


@router.get("/{attempt_id}/focus/{focus_id}", response_model=FocusDetail)
async def get_focus_detail(attempt_id: UUID, focus_id: str, container: ContainerDep) -> FocusDetail:
    return await container.get_focus_detail_use_case(attempt_id, focus_id)


@router.post("/{attempt_id}/focus/{focus_id}/reviews", response_model=FocusDetail)
async def add_focus_review(
    attempt_id: UUID, focus_id: str, body: ReviewRequest, container: ContainerDep
) -> FocusDetail:
    return await container.add_focus_review_use_case(attempt_id, focus_id, body)
