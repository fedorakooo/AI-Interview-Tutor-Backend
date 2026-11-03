from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

from shared_models.assessment import (
    Assessment,
    AssessmentCompleted,
    AssessmentContext,
    CvPolicy,
    FeedbackView,
    ReviewEntry,
    SessionEvent,
)
from shared_models.assessment.mocks import mock_assessment_context
from shared_models.cv.cv_data import CVData
from src.app.container import AppContainer, build_container
from src.domain.exceptions.session_errors import EventSeqConflictError, SessionBusyError
from src.domain.interfaces.answer_evaluator import IAnswerEvaluator
from src.domain.interfaces.assessment_completed_publisher import IAssessmentCompletedPublisher
from src.domain.interfaces.assessment_context_client import IAssessmentContextClient
from src.domain.interfaces.assessment_repository import IAssessmentRepository
from src.domain.interfaces.assessment_text_writer import IAssessmentTextWriter
from src.domain.interfaces.attempt_data_repository import IAttemptDataRepository
from src.domain.interfaces.candidate_cv_repository import ICandidateCvRepository
from src.domain.interfaces.completion_outbox_repository import ICompletionOutboxRepository
from src.domain.interfaces.feedback_repository import IFeedbackRepository
from src.domain.interfaces.feedback_writer import IFeedbackWriter
from src.domain.interfaces.interview_event_repository import IInterviewEventRepository
from src.domain.interfaces.interviewer_agent import IInterviewerAgent
from src.domain.interfaces.session_lock import ISessionLock
from src.domain.interfaces.session_presence import ISessionPresence
from src.domain.interfaces.spec_drafter import ISpecDrafter
from src.domain.interview.dto import EvaluationRequest, EvaluationResult, EvidenceDraft, InterviewerRequest
from src.domain.interview.engine import AskFocus, AskIntro
from src.domain.interview.feedback import FeedbackDigest
from src.domain.interview.report_dto import AssessmentDigest, AssessmentTexts
from src.domain.interview.spec_dto import SpecDraft


class InMemoryInterviewEventRepository(IInterviewEventRepository):
    def __init__(self) -> None:
        self.events: dict[str, list[SessionEvent]] = {}

    async def append(self, event: SessionEvent) -> None:
        stored = self.events.setdefault(event.session_id, [])
        if any(existing.seq == event.seq for existing in stored):
            raise EventSeqConflictError()
        stored.append(event)

    async def list_events(self, session_id: str) -> list[SessionEvent]:
        return sorted(self.events.get(session_id, []), key=lambda event: event.seq)


class InMemoryLock(ISessionLock):
    def __init__(self) -> None:
        self.held: set[str] = set()

    @asynccontextmanager
    async def hold(self, session_id: str) -> AsyncIterator[None]:
        if session_id in self.held:
            raise SessionBusyError()
        self.held.add(session_id)
        try:
            yield
        finally:
            self.held.discard(session_id)


class ScriptedEvaluator(IAnswerEvaluator):
    def __init__(self, result: Callable[[EvaluationRequest], EvaluationResult] | None = None) -> None:
        self.requests: list[EvaluationRequest] = []
        self.fail = False
        self._result = result or self._default_result

    @staticmethod
    def _default_result(request: EvaluationRequest) -> EvaluationResult:
        focus = request.target_focus
        return EvaluationResult(
            answer_was_complete=True,
            evidence=[
                EvidenceDraft(
                    focus_id=focus.id,
                    level="strong",
                    matched_signals=focus.strong_signals[:1],
                    quotes=[request.answer_text[:12]],
                    reasoning="Reasonable answer.",
                )
            ],
            covered_must_cover=focus.must_cover[:1],
        )

    async def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("model unavailable")
        return self._result(request)


class ScriptedInterviewer(IInterviewerAgent):
    def __init__(self) -> None:
        self.requests: list[InterviewerRequest] = []
        self.empty = False

    async def stream_message(self, request: InterviewerRequest) -> AsyncIterator[str]:
        self.requests.append(request)
        if self.empty:
            return
        action = request.action
        subject = (
            action.focus_id if isinstance(action, AskFocus) else "intro" if isinstance(action, AskIntro) else "end"
        )
        yield f"Question about {subject}"
        yield " please."


class FakeCvRepository(ICandidateCvRepository):
    def __init__(self, cv: CVData | None = None) -> None:
        self.cv = cv
        self.requested: list[UUID] = []

    async def get(self, correlation_id: UUID) -> CVData | None:
        self.requested.append(correlation_id)
        return self.cv


class RecordingPublisher(IAssessmentCompletedPublisher):
    def __init__(self) -> None:
        self.events: list[AssessmentCompleted] = []
        self.fail = False

    async def publish(self, event: AssessmentCompleted) -> None:
        if self.fail:
            raise ConnectionError("broker down")
        self.events.append(event)


FIXED_NOW = datetime(2026, 11, 2, 10, 0, tzinfo=UTC)


class InMemoryAssessmentRepository(IAssessmentRepository):
    def __init__(self) -> None:
        self.assessments: dict[UUID, Assessment] = {}
        self.reviews: list[tuple[UUID, str, ReviewEntry]] = []

    async def get(self, attempt_id: UUID) -> Assessment | None:
        return self.assessments.get(attempt_id)

    async def save(self, assessment: Assessment) -> None:
        self.assessments.setdefault(assessment.attempt_id, assessment)

    async def add_review(self, attempt_id: UUID, focus_id: str, entry: ReviewEntry) -> None:
        self.reviews.append((attempt_id, focus_id, entry))

    async def list_reviews(self, attempt_id: UUID) -> dict[str, list[ReviewEntry]]:
        grouped: dict[str, list[ReviewEntry]] = {}
        for stored_attempt, focus_id, entry in self.reviews:
            if stored_attempt == attempt_id:
                grouped.setdefault(focus_id, []).append(entry)
        return grouped


class ScriptedTextWriter(IAssessmentTextWriter):
    def __init__(self, texts: AssessmentTexts | None = None) -> None:
        self.texts = texts
        self.digests: list[AssessmentDigest] = []
        self.fail = False

    async def write(self, digest: AssessmentDigest) -> AssessmentTexts:
        self.digests.append(digest)
        if self.fail or self.texts is None:
            raise RuntimeError("model unavailable")
        return self.texts


class InMemoryCompletionOutboxRepository(ICompletionOutboxRepository):
    def __init__(self) -> None:
        self.events: dict[UUID, AssessmentCompleted] = {}
        self.published: set[UUID] = set()

    async def enqueue(self, event: AssessmentCompleted) -> None:
        self.events.setdefault(event.event_id, event)

    async def list_pending(self, limit: int) -> list[AssessmentCompleted]:
        return [e for e in self.events.values() if e.event_id not in self.published][:limit]

    async def mark_published(self, event_id: UUID) -> None:
        self.published.add(event_id)


class InMemoryPresence(ISessionPresence):
    def __init__(self) -> None:
        self.current: dict[str, str] = {}
        self.counter = 0

    async def claim(self, session_id: str) -> str:
        self.counter += 1
        token = f"connection-{self.counter}"
        self.current[session_id] = token
        return token

    async def release(self, session_id: str, token: str) -> bool:
        if self.current.get(session_id) == token:
            del self.current[session_id]
            return True
        return False


class InMemoryFeedbackRepository(IFeedbackRepository):
    def __init__(self) -> None:
        self.versions: list[FeedbackView] = []

    async def latest(self, attempt_id: UUID) -> FeedbackView | None:
        return max((v for v in self.versions if v.attempt_id == attempt_id), key=lambda v: v.version, default=None)

    async def append(self, feedback: FeedbackView) -> bool:
        if any(v.attempt_id == feedback.attempt_id and v.version == feedback.version for v in self.versions):
            return False
        self.versions.append(feedback)
        return True


class ScriptedFeedbackWriter(IFeedbackWriter):
    def __init__(self, text: str | None = "Thank you! You did well on Python fundamentals.") -> None:
        self.text = text
        self.digests: list[FeedbackDigest] = []

    async def write(self, digest: FeedbackDigest) -> str:
        self.digests.append(digest)
        if self.text is None:
            raise RuntimeError("model unavailable")
        return self.text


class FakeSpecDrafter(ISpecDrafter):
    def __init__(self, draft: SpecDraft | Exception | None = None) -> None:
        self.draft_or_error = draft if draft is not None else SpecDraft()

    async def draft(self, request) -> SpecDraft:
        if isinstance(self.draft_or_error, Exception):
            raise self.draft_or_error
        return self.draft_or_error


class FakeContextClient(IAssessmentContextClient):
    def __init__(self, context: AssessmentContext, error: Exception | None = None) -> None:
        self.context = context
        self.error = error
        self.requested: list[UUID] = []

    async def get_context(self, attempt_id: UUID) -> AssessmentContext:
        self.requested.append(attempt_id)
        if self.error is not None:
            raise self.error
        return self.context


class InMemoryAttemptDataRepository(IAttemptDataRepository):
    def __init__(self) -> None:
        self.erased: list[tuple[UUID, UUID | None]] = []

    async def erase(self, attempt_id: UUID, cv_correlation_id: UUID | None) -> dict[str, int]:
        self.erased.append((attempt_id, cv_correlation_id))
        return {"events": 0}


class FakeStack:
    """The real use cases wired to in-memory fakes."""

    def __init__(
        self,
        *,
        context: AssessmentContext | None = None,
        context_error: Exception | None = None,
        cv: CVData | None = CVData(),
        now: datetime = FIXED_NOW,
        evaluator: IAnswerEvaluator | None = None,
        text_writer: IAssessmentTextWriter | None = None,
        feedback_writer: IFeedbackWriter | None = None,
        spec_drafter: ISpecDrafter | None = None,
        attempt_data_repository: IAttemptDataRepository | None = None,
        token_verifier=None,
    ) -> None:
        self.now = now
        self.context = context or mock_assessment_context(CvPolicy.REQUIRED)
        self.event_repository = InMemoryInterviewEventRepository()
        self.assessment_repository = InMemoryAssessmentRepository()
        self.feedback_repository = InMemoryFeedbackRepository()
        self.completion_outbox_repository = InMemoryCompletionOutboxRepository()
        self.attempt_data_repository = attempt_data_repository or InMemoryAttemptDataRepository()
        self.cv_repository = FakeCvRepository(cv)
        self.lock = InMemoryLock()
        self.presence = InMemoryPresence()
        self.evaluator = evaluator or ScriptedEvaluator()
        self.interviewer = ScriptedInterviewer()
        self.text_writer = text_writer or ScriptedTextWriter()
        self.feedback_writer = feedback_writer or ScriptedFeedbackWriter()
        self.spec_drafter = spec_drafter or FakeSpecDrafter()
        self.publisher = RecordingPublisher()
        self.context_client = FakeContextClient(self.context, context_error)
        self.container: AppContainer = build_container(
            None,
            None,
            None,
            event_repository=self.event_repository,
            assessment_repository=self.assessment_repository,
            feedback_repository=self.feedback_repository,
            completion_outbox_repository=self.completion_outbox_repository,
            attempt_data_repository=self.attempt_data_repository,
            cv_repository=self.cv_repository,
            lock=self.lock,
            presence=self.presence,
            evaluator=self.evaluator,
            interviewer=self.interviewer,
            assessment_text_writer=self.text_writer,
            feedback_writer=self.feedback_writer,
            spec_drafter=self.spec_drafter,
            completed_publisher=self.publisher,
            context_client=self.context_client,
            token_verifier=token_verifier,
            clock=lambda: self.now,
        )
