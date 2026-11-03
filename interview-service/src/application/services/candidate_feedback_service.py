import logging
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from shared_models.assessment import FeedbackView

from src.application.interfaces.candidate_feedback_service import ICandidateFeedbackService
from src.application.mappers.feedback_view_mapper import FeedbackViewMapper
from src.application.services.report_loader import ReportLoader
from src.domain.entities.assessment import Assessment
from src.domain.entities.feedback_entry import FeedbackEntry
from src.domain.exceptions.feedback_errors import FeedbackDisabledError, FeedbackLeakError
from src.domain.interfaces.ai.feedback_writer import IFeedbackWriter
from src.domain.interfaces.clients.assessment_context_client import IAssessmentContextClient
from src.domain.interfaces.repositories.feedback_repository import IFeedbackRepository
from src.domain.services.feedback_digest_builder import FeedbackDigestBuilder
from src.domain.services.feedback_fallback_builder import FeedbackFallbackBuilder
from src.domain.services.feedback_leak_detector import FeedbackLeakDetector
from src.domain.value_objects.interview_template import InterviewTemplate

logger = logging.getLogger(__name__)


class CandidateFeedbackService(ICandidateFeedbackService):
    def __init__(
        self,
        report_loader: ReportLoader,
        feedback_repository: IFeedbackRepository,
        feedback_writer: IFeedbackWriter,
        context_client: IAssessmentContextClient,
        clock: Callable[[], datetime],
    ) -> None:
        self._report_loader = report_loader
        self._feedback_repository = feedback_repository
        self._writer = feedback_writer
        self._context_client = context_client
        self._clock = clock

    async def get(self, attempt_id: UUID) -> FeedbackView:
        template = (await self._context_client.get_context(attempt_id)).template
        return FeedbackViewMapper.to_view(await self._current(attempt_id, template))

    async def edit(self, attempt_id: UUID, editor_id: UUID, text: str) -> FeedbackView:
        template = (await self._context_client.get_context(attempt_id)).template
        current = await self._current(attempt_id, template)
        assessment, _ = await self._report_loader.load(attempt_id, template)
        if FeedbackLeakDetector.find(text, template, self._review_comments(assessment)):
            raise FeedbackLeakError()
        feedback = FeedbackEntry(
            attempt_id=attempt_id,
            version=current.version + 1,
            text=text.strip(),
            source="edited",
            editor_id=editor_id,
            created_at=self._clock(),
        )
        if not await self._feedback_repository.append(feedback):
            return FeedbackViewMapper.to_view(await self._current(attempt_id, template))
        return FeedbackViewMapper.to_view(feedback)

    async def _current(self, attempt_id: UUID, template: InterviewTemplate) -> FeedbackEntry:
        if not template.candidate_feedback:
            raise FeedbackDisabledError()
        assessment, _ = await self._report_loader.load(attempt_id, template)
        stored = await self._feedback_repository.latest(attempt_id)
        if stored is not None:
            return stored

        digest = FeedbackDigestBuilder.build(assessment, template)
        try:
            text = await self._writer.write(digest)
            if FeedbackLeakDetector.find(text, template, self._review_comments(assessment)):
                raise FeedbackLeakError()
        except Exception:
            logger.exception("Writing candidate feedback failed for attempt %s", attempt_id)
            text = FeedbackFallbackBuilder.build(digest)

        feedback = FeedbackEntry(
            attempt_id=attempt_id, version=1, text=text[:4000], source="generated", created_at=self._clock()
        )
        await self._feedback_repository.append(feedback)
        return await self._feedback_repository.latest(attempt_id) or feedback

    @staticmethod
    def _review_comments(assessment: Assessment) -> list[str]:
        return [entry.comment for item in assessment.focus for entry in item.review]
