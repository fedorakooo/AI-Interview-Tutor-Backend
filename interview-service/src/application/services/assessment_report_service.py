from collections.abc import Callable
from datetime import datetime
from uuid import UUID, uuid4

from shared_models.assessment import AssessmentOverview, FocusDetail, ReviewRequest

from src.application.interfaces.assessment_report_service import IAssessmentReportService
from src.application.mappers.report_view_mapper import ReportViewMapper
from src.application.mappers.review_mapper import ReviewMapper
from src.application.services.report_loader import ReportLoader
from src.domain.exceptions.report_errors import FocusNotFoundError
from src.domain.interfaces.clients.assessment_context_client import IAssessmentContextClient
from src.domain.interfaces.repositories.assessment_repository import IAssessmentRepository
from src.domain.value_objects.interview_template import InterviewTemplate


class AssessmentReportService(IAssessmentReportService):
    def __init__(
        self,
        report_loader: ReportLoader,
        assessment_repository: IAssessmentRepository,
        context_client: IAssessmentContextClient,
        clock: Callable[[], datetime],
    ) -> None:
        self._report_loader = report_loader
        self._assessment_repository = assessment_repository
        self._context_client = context_client
        self._clock = clock

    async def get_overview(self, attempt_id: UUID) -> AssessmentOverview:
        template = (await self._context_client.get_context(attempt_id)).template
        assessment, _ = await self._report_loader.load(attempt_id, template)
        return ReportViewMapper.overview(assessment, template)

    async def get_focus_detail(self, attempt_id: UUID, focus_id: str) -> FocusDetail:
        template = (await self._context_client.get_context(attempt_id)).template
        assessment, state = await self._report_loader.load(attempt_id, template)
        self._require_focus(template, focus_id)
        return ReportViewMapper.focus_detail(assessment, template, state, focus_id)

    async def add_review(self, attempt_id: UUID, focus_id: str, request: ReviewRequest) -> FocusDetail:
        template = (await self._context_client.get_context(attempt_id)).template
        await self._report_loader.load(attempt_id, template)
        self._require_focus(template, focus_id)
        await self._assessment_repository.add_review(
            attempt_id, focus_id, ReviewMapper.to_entry(request, uuid4(), self._clock())
        )
        assessment, state = await self._report_loader.load(attempt_id, template)
        return ReportViewMapper.focus_detail(assessment, template, state, focus_id)

    @staticmethod
    def _require_focus(template: InterviewTemplate, focus_id: str) -> None:
        if focus_id not in {focus.id for focus in template.criteria}:
            raise FocusNotFoundError()
