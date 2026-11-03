from uuid import UUID

from fastapi import APIRouter, Depends
from shared_models.assessment import FeedbackEditRequest, FeedbackView

from src.api.dependencies.container import ContainerDep
from src.api.security import require_internal_service

router = APIRouter(
    prefix="/api/internal/feedback",
    tags=["Internal feedback"],
    dependencies=[Depends(require_internal_service)],
)


@router.get("/{attempt_id}", response_model=FeedbackView)
async def get_feedback(attempt_id: UUID, container: ContainerDep) -> FeedbackView:
    return await container.candidate_feedback_service.get(attempt_id)


@router.put("/{attempt_id}", response_model=FeedbackView)
async def edit_feedback(attempt_id: UUID, body: FeedbackEditRequest, container: ContainerDep) -> FeedbackView:
    return await container.candidate_feedback_service.edit(attempt_id, body.editor_id, body.text)
