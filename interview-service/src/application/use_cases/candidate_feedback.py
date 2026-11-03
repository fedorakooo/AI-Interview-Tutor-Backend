from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from shared_models.assessment import Assessment, AssessmentTemplateSnapshot, FeedbackView

from src.application.services.assessment_report_service import AssessmentReportService
from src.domain.exceptions.feedback_errors import FeedbackDisabledError, FeedbackLeakError
from src.domain.interfaces.feedback_repository import IFeedbackRepository
from src.domain.interfaces.feedback_writer import IFeedbackWriter
from src.domain.interview.feedback import build_digest, fallback_text, find_leaks
from src.logger import app_logger


def _require_enabled(template: AssessmentTemplateSnapshot) -> None:
    if not template.candidate_feedback:
        raise FeedbackDisabledError()


def _review_comments(assessment: Assessment) -> list[str]:
    return [entry.comment for item in assessment.focus for entry in item.review]


class GetCandidateFeedbackUseCase:
    def __init__(
        self,
        report_service: AssessmentReportService,
        feedback_repository: IFeedbackRepository,
        feedback_writer: IFeedbackWriter,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._reports = report_service
        self._feedback_repository = feedback_repository
        self._writer = feedback_writer
        self._clock = clock

    async def __call__(self, attempt_id: UUID, template: AssessmentTemplateSnapshot) -> FeedbackView:
        _require_enabled(template)
        assessment, _ = await self._reports.load(attempt_id, template)
        stored = await self._feedback_repository.latest(attempt_id)
        if stored is not None:
            return stored

        digest = build_digest(assessment, template)
        try:
            text = await self._writer.write(digest)
            if find_leaks(text, template, _review_comments(assessment)):
                raise FeedbackLeakError()
        except Exception:
            app_logger.exception("Writing candidate feedback failed for attempt %s", attempt_id)
            text = fallback_text(digest)

        feedback = FeedbackView(
            attempt_id=attempt_id, version=1, text=text[:4000], source="generated", created_at=self._clock()
        )
        await self._feedback_repository.append(feedback)
        return await self._feedback_repository.latest(attempt_id) or feedback


class EditCandidateFeedbackUseCase:
    def __init__(
        self,
        report_service: AssessmentReportService,
        feedback_repository: IFeedbackRepository,
        get_feedback: GetCandidateFeedbackUseCase,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._reports = report_service
        self._feedback_repository = feedback_repository
        self._get_feedback = get_feedback
        self._clock = clock

    async def __call__(
        self, attempt_id: UUID, template: AssessmentTemplateSnapshot, editor_id: UUID, text: str
    ) -> FeedbackView:
        current = await self._get_feedback(attempt_id, template)
        assessment, _ = await self._reports.load(attempt_id, template)
        if find_leaks(text, template, _review_comments(assessment)):
            raise FeedbackLeakError()
        feedback = FeedbackView(
            attempt_id=attempt_id,
            version=current.version + 1,
            text=text.strip(),
            source="edited",
            editor_id=editor_id,
            created_at=self._clock(),
        )
        if not await self._feedback_repository.append(feedback):
            return await self._get_feedback(attempt_id, template)
        return feedback
