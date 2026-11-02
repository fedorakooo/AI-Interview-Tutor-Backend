from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from shared_models.assessment import (
    Assessment,
    AssessmentOverview,
    AssessmentTemplateSnapshot,
    FocusDetail,
    ReviewEntry,
    ReviewRequest,
    SessionState,
    build_focus_detail,
    build_overview,
    compute_focus_verdict,
    fold_events,
    verify_assessment,
)
from shared_models.assessment.session_state import SessionStatus

from src.domain.exceptions.report_errors import FocusNotFoundError, ReportNotReadyError
from src.domain.interfaces.assessment_store import IAssessmentStore
from src.domain.interfaces.assessment_text_writer import IAssessmentTextWriter
from src.domain.interfaces.event_journal import IEventJournal
from src.domain.interview.report_builder import build_assessment
from src.domain.interview.report_dto import AssessmentDigest, AssessmentTexts
from src.logger import app_logger

GENERATOR_VERSION = "assessment-1"


class AssessmentReportService:
    def __init__(
        self,
        journal: IEventJournal,
        store: IAssessmentStore,
        text_writer: IAssessmentTextWriter,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._journal = journal
        self._store = store
        self._text_writer = text_writer
        self._clock = clock

    async def overview(self, attempt_id: UUID, template: AssessmentTemplateSnapshot) -> AssessmentOverview:
        assessment, _ = await self._load(attempt_id, template)
        return build_overview(assessment, template)

    async def focus_detail(self, attempt_id: UUID, template: AssessmentTemplateSnapshot, focus_id: str) -> FocusDetail:
        assessment, state = await self._load(attempt_id, template)
        if focus_id not in {focus.id for focus in template.criteria}:
            raise FocusNotFoundError()
        return build_focus_detail(assessment, template, state, focus_id)

    async def add_review(
        self, attempt_id: UUID, template: AssessmentTemplateSnapshot, focus_id: str, request: ReviewRequest
    ) -> FocusDetail:
        await self._load(attempt_id, template)
        if focus_id not in {focus.id for focus in template.criteria}:
            raise FocusNotFoundError()
        await self._store.add_review(
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
        return await self.focus_detail(attempt_id, template, focus_id)

    async def _load(self, attempt_id: UUID, template: AssessmentTemplateSnapshot) -> tuple[Assessment, SessionState]:
        events = await self._journal.list_events(str(attempt_id))
        if not events:
            raise ReportNotReadyError()
        state = fold_events(events)
        if state.status != SessionStatus.COMPLETED:
            raise ReportNotReadyError()

        assessment = await self._store.get(attempt_id)
        if assessment is None:
            assessment = await self._generate(attempt_id, template, events, state)
            await self._store.save(assessment)
            assessment = await self._store.get(attempt_id) or assessment
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
            app_logger.exception("Writing report texts failed for session %s", state.session_id)
        assessment = build_assessment(attempt_id, template, events, texts, GENERATOR_VERSION, self._clock())
        verify_assessment(assessment, template, events)
        return assessment

    async def _with_reviews(self, attempt_id: UUID, assessment: Assessment) -> Assessment:
        reviews = await self._store.list_reviews(attempt_id)
        focus = [item.model_copy(update={"review": reviews.get(item.focus_id, [])}) for item in assessment.focus]
        return assessment.model_copy(update={"focus": focus})
