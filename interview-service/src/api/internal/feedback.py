from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from shared_models.assessment import FeedbackEditRequest, FeedbackView

from src.api.internal.auth import require_internal_service
from src.api.internal.dependencies import ContextClientDep, template_for_attempt
from src.application.interview.feedback_service import CandidateFeedbackService
from src.domain.exceptions.feedback_errors import FeedbackDisabledError, FeedbackLeakError
from src.domain.exceptions.report_errors import ReportNotReadyError

router = APIRouter(
    prefix="/api/internal/feedback",
    tags=["Internal feedback"],
    dependencies=[Depends(require_internal_service)],
)


def get_feedback_service(request: Request) -> CandidateFeedbackService:
    return request.app.state.candidate_feedback_service


FeedbackServiceDep = Annotated[CandidateFeedbackService, Depends(get_feedback_service)]


def _map(exc: Exception) -> HTTPException:
    if isinstance(exc, ReportNotReadyError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Report is not ready")
    if isinstance(exc, FeedbackDisabledError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate feedback is disabled")
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Text contains internal details")


@router.get("/{attempt_id}", response_model=FeedbackView)
async def get_feedback(attempt_id: UUID, service: FeedbackServiceDep, context_client: ContextClientDep) -> FeedbackView:
    template = await template_for_attempt(context_client, attempt_id)
    try:
        return await service.get(attempt_id, template)
    except (ReportNotReadyError, FeedbackDisabledError) as exc:
        raise _map(exc) from exc


@router.put("/{attempt_id}", response_model=FeedbackView)
async def edit_feedback(
    attempt_id: UUID, body: FeedbackEditRequest, service: FeedbackServiceDep, context_client: ContextClientDep
) -> FeedbackView:
    template = await template_for_attempt(context_client, attempt_id)
    try:
        return await service.edit(attempt_id, template, body.editor_id, body.text)
    except (ReportNotReadyError, FeedbackDisabledError, FeedbackLeakError) as exc:
        raise _map(exc) from exc
