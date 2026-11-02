from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from shared_models.assessment import AssessmentOverview, AssessmentTemplateSnapshot, FocusDetail, ReviewRequest

from src.api.internal.auth import require_internal_service
from src.application.interview.report_service import AssessmentReportService
from src.domain.exceptions.assessment_context_errors import (
    AssessmentContextNotFoundError,
    AssessmentContextUnavailableError,
    AssessmentNotReadyError,
)
from src.domain.exceptions.report_errors import FocusNotFoundError, ReportNotReadyError
from src.domain.interfaces.assessment_context_client import IAssessmentContextClient

router = APIRouter(
    prefix="/api/internal/reports",
    tags=["Internal reports"],
    dependencies=[Depends(require_internal_service)],
)


def get_report_service(request: Request) -> AssessmentReportService:
    return request.app.state.assessment_report_service


def get_context_client(request: Request) -> IAssessmentContextClient:
    return request.app.state.assessment_context_client


ReportServiceDep = Annotated[AssessmentReportService, Depends(get_report_service)]
ContextClientDep = Annotated[IAssessmentContextClient, Depends(get_context_client)]


async def _template(context_client: IAssessmentContextClient, attempt_id: UUID) -> AssessmentTemplateSnapshot:
    try:
        return (await context_client.get_context(attempt_id)).template
    except AssessmentContextNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found") from exc
    except AssessmentNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Report is not ready") from exc
    except AssessmentContextUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Context unavailable") from exc


def _map(exc: Exception) -> HTTPException:
    if isinstance(exc, ReportNotReadyError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Report is not ready")
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Focus area not found")


@router.get("/{attempt_id}", response_model=AssessmentOverview)
async def get_overview(
    attempt_id: UUID, service: ReportServiceDep, context_client: ContextClientDep
) -> AssessmentOverview:
    template = await _template(context_client, attempt_id)
    try:
        return await service.overview(attempt_id, template)
    except (ReportNotReadyError, FocusNotFoundError) as exc:
        raise _map(exc) from exc


@router.get("/{attempt_id}/focus/{focus_id}", response_model=FocusDetail)
async def get_focus_detail(
    attempt_id: UUID, focus_id: str, service: ReportServiceDep, context_client: ContextClientDep
) -> FocusDetail:
    template = await _template(context_client, attempt_id)
    try:
        return await service.focus_detail(attempt_id, template, focus_id)
    except (ReportNotReadyError, FocusNotFoundError) as exc:
        raise _map(exc) from exc


@router.post("/{attempt_id}/focus/{focus_id}/reviews", response_model=FocusDetail)
async def add_focus_review(
    attempt_id: UUID,
    focus_id: str,
    body: ReviewRequest,
    service: ReportServiceDep,
    context_client: ContextClientDep,
) -> FocusDetail:
    template = await _template(context_client, attempt_id)
    try:
        return await service.add_review(attempt_id, template, focus_id, body)
    except (ReportNotReadyError, FocusNotFoundError) as exc:
        raise _map(exc) from exc
