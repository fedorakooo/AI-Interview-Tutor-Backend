from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

from shared_models.assessment import Assessment, AssessmentCompleted, ReviewEntry, SessionEvent
from shared_models.cv.cv_data import CVData
from src.domain.exceptions.session_errors import EventSeqConflictError, SessionBusyError
from src.domain.interfaces.answer_evaluator import IAnswerEvaluator
from src.domain.interfaces.assessment_completed_publisher import IAssessmentCompletedPublisher
from src.domain.interfaces.assessment_store import IAssessmentStore
from src.domain.interfaces.assessment_text_writer import IAssessmentTextWriter
from src.domain.interfaces.candidate_cv_provider import ICandidateCvProvider
from src.domain.interfaces.completion_outbox import ICompletionOutbox
from src.domain.interfaces.event_journal import IEventJournal
from src.domain.interfaces.interviewer_agent import IInterviewerAgent
from src.domain.interfaces.session_lock import ISessionLock
from src.domain.interfaces.session_presence import ISessionPresence
from src.domain.interview.dto import EvaluationRequest, EvaluationResult, EvidenceDraft, InterviewerRequest
from src.domain.interview.engine import AskFocus, AskIntro
from src.domain.interview.report_dto import AssessmentDigest, AssessmentTexts


class InMemoryJournal(IEventJournal):
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


class FakeCvProvider(ICandidateCvProvider):
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


class InMemoryAssessmentStore(IAssessmentStore):
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


class InMemoryCompletionOutbox(ICompletionOutbox):
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
