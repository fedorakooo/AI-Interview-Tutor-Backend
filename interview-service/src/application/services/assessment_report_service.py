import logging
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from shared_models.assessment import (
    Assessment,
    AssessmentTemplateSnapshot,
    InconsistentAssessmentError,
    SessionState,
    compute_focus_verdict,
    verify_assessment,
)
from shared_models.assessment.session_state import SessionStatus

from src.application.services.session_journal import fold_journal
from src.domain.exceptions.report_errors import InconsistentReportError, ReportNotReadyError
from src.domain.interfaces.assessment_repository import IAssessmentRepository
from src.domain.interfaces.assessment_text_writer import IAssessmentTextWriter
from src.domain.interfaces.interview_event_repository import IInterviewEventRepository
from src.domain.interview.report_builder import build_assessment
from src.domain.interview.report_dto import AssessmentDigest, AssessmentTexts

logger = logging.getLogger(__name__)

GENERATOR_VERSION = "assessment-1"


class AssessmentReportService:
    def __init__(
        self,
        event_repository: IInterviewEventRepository,
        assessment_repository: IAssessmentRepository,
        text_writer: IAssessmentTextWriter,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._event_repository = event_repository
        self._assessment_repository = assessment_repository
        self._text_writer = text_writer
        self._clock = clock

    async def load(self, attempt_id: UUID, template: AssessmentTemplateSnapshot) -> tuple[Assessment, SessionState]:
        events = await self._event_repository.list_events(str(attempt_id))
        if not events:
            raise ReportNotReadyError()
        state = fold_journal(events)
        if state.status != SessionStatus.COMPLETED:
            raise ReportNotReadyError()

        assessment = await self._assessment_repository.get(attempt_id)
        if assessment is None:
            assessment = await self._generate(attempt_id, template, events, state)
            await self._assessment_repository.save(assessment)
            assessment = await self._assessment_repository.get(attempt_id) or assessment
        return await self._with_reviews(attempt_id, assessment), state

    async def _generate(
        self, attempt_id: UUID, template: AssessmentTemplateSnapshot, events: list, state: SessionState
    ) -> Assessment:
        verdicts = {
            focus.id: compute_focus_verdict(focus, [item for item in state.evidence if item.focus_id == focus.id])
            for focus in template.criteria
        }
        texts: AssessmentTexts | None = None
        try:
            texts = await self._text_writer.write(AssessmentDigest(template=template, state=state, verdicts=verdicts))
        except Exception:
            logger.exception("Writing report texts failed for session %s", state.session_id)
        assessment = build_assessment(attempt_id, template, events, texts, GENERATOR_VERSION, self._clock())
        try:
            verify_assessment(assessment, template, events)
        except InconsistentAssessmentError as exc:
            raise InconsistentReportError() from exc
        return assessment

    async def _with_reviews(self, attempt_id: UUID, assessment: Assessment) -> Assessment:
        reviews = await self._assessment_repository.list_reviews(attempt_id)
        focus = [item.model_copy(update={"review": reviews.get(item.focus_id, [])}) for item in assessment.focus]
        return assessment.model_copy(update={"focus": focus})
