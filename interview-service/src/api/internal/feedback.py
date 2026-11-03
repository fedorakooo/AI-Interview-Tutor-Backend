from uuid import UUID

from fastapi import APIRouter, Depends
from shared_models.assessment import FeedbackEditRequest, FeedbackView

from src.api.dependencies.container import ContainerDep
from src.api.dependencies.internal import template_for_attempt
from src.api.security import require_internal_service

router = APIRouter(
    prefix="/api/internal/feedback",
    tags=["Internal feedback"],
    dependencies=[Depends(require_internal_service)],
)


@router.get("/{attempt_id}", response_model=FeedbackView)
async def get_feedback(attempt_id: UUID, container: ContainerDep) -> FeedbackView:
    template = await template_for_attempt(container, attempt_id)
    return await container.get_candidate_feedback_use_case(attempt_id, template)


@router.put("/{attempt_id}", response_model=FeedbackView)
async def edit_feedback(attempt_id: UUID, body: FeedbackEditRequest, container: ContainerDep) -> FeedbackView:
    template = await template_for_attempt(container, attempt_id)
    return await container.edit_candidate_feedback_use_case(attempt_id, template, body.editor_id, body.text)
