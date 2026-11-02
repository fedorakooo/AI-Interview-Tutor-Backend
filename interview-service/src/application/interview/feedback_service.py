from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from shared_models.assessment import AssessmentTemplateSnapshot, FeedbackView

from src.application.interview.report_service import AssessmentReportService
from src.domain.exceptions.feedback_errors import FeedbackDisabledError, FeedbackLeakError
from src.domain.interfaces.feedback_store import IFeedbackStore
from src.domain.interfaces.feedback_writer import IFeedbackWriter
from src.domain.interview.feedback import build_digest, fallback_text, find_leaks
from src.logger import app_logger


class CandidateFeedbackService:
    def __init__(
        self,
        reports: AssessmentReportService,
        store: IFeedbackStore,
        writer: IFeedbackWriter,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._reports = reports
        self._store = store
        self._writer = writer
        self._clock = clock

    async def get(self, attempt_id: UUID, template: AssessmentTemplateSnapshot) -> FeedbackView:
        self._require_enabled(template)
        assessment = await self._reports.assessment(attempt_id, template)
        stored = await self._store.latest(attempt_id)
        if stored is not None:
            return stored

        digest = build_digest(assessment, template)
        try:
            text = await self._writer.write(digest)
            if find_leaks(text, template, self._comments(assessment)):
                raise FeedbackLeakError()
        except Exception:
            app_logger.exception("Writing candidate feedback failed for attempt %s", attempt_id)
            text = fallback_text(digest)

        feedback = FeedbackView(
            attempt_id=attempt_id, version=1, text=text[:4000], source="generated", created_at=self._clock()
        )
        await self._store.append(feedback)
        return await self._store.latest(attempt_id) or feedback

    async def edit(
        self, attempt_id: UUID, template: AssessmentTemplateSnapshot, editor_id: UUID, text: str
    ) -> FeedbackView:
        current = await self.get(attempt_id, template)
        assessment = await self._reports.assessment(attempt_id, template)
        if find_leaks(text, template, self._comments(assessment)):
            raise FeedbackLeakError()
        feedback = FeedbackView(
            attempt_id=attempt_id,
            version=current.version + 1,
            text=text.strip(),
            source="edited",
            editor_id=editor_id,
            created_at=self._clock(),
        )
        if not await self._store.append(feedback):
            return await self.get(attempt_id, template)
        return feedback

    @staticmethod
    def _require_enabled(template: AssessmentTemplateSnapshot) -> None:
        if not template.candidate_feedback:
            raise FeedbackDisabledError()

    @staticmethod
    def _comments(assessment) -> list[str]:
        return [entry.comment for item in assessment.focus for entry in item.review]
