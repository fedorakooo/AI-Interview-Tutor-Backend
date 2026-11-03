import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from uuid import UUID

from src.domain.entities.assessment import Assessment
from src.domain.entities.session_state import SessionState
from src.domain.enums.session_status import SessionStatus
from src.domain.events.session_event import SessionEvent
from src.domain.exceptions.report_errors import ReportNotReadyError
from src.domain.interfaces.ai.assessment_text_writer import IAssessmentTextWriter
from src.domain.interfaces.repositories.assessment_repository import IAssessmentRepository
from src.domain.interfaces.repositories.interview_event_repository import IInterviewEventRepository
from src.domain.services.assessment_builder import AssessmentBuilder
from src.domain.services.assessment_verifier import AssessmentVerifier
from src.domain.services.focus_verdict_calculator import FocusVerdictCalculator
from src.domain.services.journal_folder import JournalFolder
from src.domain.value_objects.assessment_digest import AssessmentDigest
from src.domain.value_objects.assessment_texts import AssessmentTexts
from src.domain.value_objects.interview_template import InterviewTemplate

logger = logging.getLogger(__name__)

GENERATOR_VERSION = "assessment-1"


class ReportLoader:
    def __init__(
        self,
        event_repository: IInterviewEventRepository,
        assessment_repository: IAssessmentRepository,
        text_writer: IAssessmentTextWriter,
        clock: Callable[[], datetime],
    ) -> None:
        self._event_repository = event_repository
        self._assessment_repository = assessment_repository
        self._text_writer = text_writer
        self._clock = clock

    async def load(self, attempt_id: UUID, template: InterviewTemplate) -> tuple[Assessment, SessionState]:
        events = await self._event_repository.list_events(str(attempt_id))
        if not events:
            raise ReportNotReadyError()
        state = JournalFolder.fold(events)
        if state.status != SessionStatus.COMPLETED:
            raise ReportNotReadyError()

        assessment = await self._assessment_repository.get(attempt_id)
        if assessment is None:
            assessment = await self._generate(attempt_id, template, events, state)
            await self._assessment_repository.save(assessment)
            assessment = await self._assessment_repository.get(attempt_id) or assessment
        return await self._with_reviews(attempt_id, assessment), state

    async def _generate(
        self, attempt_id: UUID, template: InterviewTemplate, events: list[SessionEvent], state: SessionState
    ) -> Assessment:
        verdicts = {
            focus.id: FocusVerdictCalculator.compute(
                focus, [item for item in state.evidence if item.focus_id == focus.id]
            )
            for focus in template.criteria
        }
        texts: AssessmentTexts | None = None
        try:
            texts = await self._text_writer.write(AssessmentDigest(template=template, state=state, verdicts=verdicts))
        except Exception:
            logger.exception("Writing report texts failed for session %s", state.session_id)
        assessment = AssessmentBuilder.build(attempt_id, template, state, texts, GENERATOR_VERSION, self._clock())
        AssessmentVerifier.verify(assessment, template, events)
        return assessment

    async def _with_reviews(self, attempt_id: UUID, assessment: Assessment) -> Assessment:
        reviews = await self._assessment_repository.list_reviews(attempt_id)
        focus = tuple(replace(item, review=tuple(reviews.get(item.focus_id, []))) for item in assessment.focus)
        return replace(assessment, focus=focus)
