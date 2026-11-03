from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from shared_models.assessment import (
    AssessmentOverview,
    AssessmentTemplateSnapshot,
    FocusDetail,
    ReviewEntry,
    ReviewRequest,
    build_focus_detail,
    build_overview,
)

from src.application.services.assessment_report_service import AssessmentReportService
from src.domain.exceptions.report_errors import FocusNotFoundError
from src.domain.interfaces.assessment_context_client import IAssessmentContextClient
from src.domain.interfaces.assessment_repository import IAssessmentRepository


def _require_focus(template: AssessmentTemplateSnapshot, focus_id: str) -> None:
    if focus_id not in {focus.id for focus in template.criteria}:
        raise FocusNotFoundError()


class GetAssessmentOverviewUseCase:
    def __init__(self, report_service: AssessmentReportService, context_client: IAssessmentContextClient):
        self._reports = report_service
        self._context_client = context_client

    async def __call__(self, attempt_id: UUID) -> AssessmentOverview:
        template = (await self._context_client.get_context(attempt_id)).template
        assessment, _ = await self._reports.load(attempt_id, template)
        return build_overview(assessment, template)


class GetFocusDetailUseCase:
    def __init__(self, report_service: AssessmentReportService, context_client: IAssessmentContextClient):
        self._reports = report_service
        self._context_client = context_client

    async def __call__(self, attempt_id: UUID, focus_id: str) -> FocusDetail:
        template = (await self._context_client.get_context(attempt_id)).template
        assessment, state = await self._reports.load(attempt_id, template)
        _require_focus(template, focus_id)
        return build_focus_detail(assessment, template, state, focus_id)


class AddFocusReviewUseCase:
    def __init__(
        self,
        report_service: AssessmentReportService,
        assessment_repository: IAssessmentRepository,
        context_client: IAssessmentContextClient,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._reports = report_service
        self._assessment_repository = assessment_repository
        self._context_client = context_client
        self._clock = clock

    async def __call__(self, attempt_id: UUID, focus_id: str, request: ReviewRequest) -> FocusDetail:
        template = (await self._context_client.get_context(attempt_id)).template
        await self._reports.load(attempt_id, template)
        _require_focus(template, focus_id)
        await self._assessment_repository.add_review(
            attempt_id,
            focus_id,
            ReviewEntry(
                review_id=uuid4(),
                author_id=request.author_id,
                created_at=self._clock(),
                comment=request.comment,
                manual_verdict=request.manual_verdict,
            ),
        )
        assessment, state = await self._reports.load(attempt_id, template)
        return build_focus_detail(assessment, template, state, focus_id)
