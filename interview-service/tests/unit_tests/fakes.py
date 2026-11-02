from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

from shared_models.assessment import AssessmentCompleted, SessionEvent
from shared_models.cv.cv_data import CVData
from src.domain.exceptions.session_errors import EventSeqConflictError, SessionBusyError
from src.domain.interfaces.answer_evaluator import IAnswerEvaluator
from src.domain.interfaces.assessment_completed_publisher import IAssessmentCompletedPublisher
from src.domain.interfaces.candidate_cv_provider import ICandidateCvProvider
from src.domain.interfaces.event_journal import IEventJournal
from src.domain.interfaces.interviewer_agent import IInterviewerAgent
from src.domain.interfaces.session_lock import ISessionLock
from src.domain.interview.dto import EvaluationRequest, EvaluationResult, EvidenceDraft, InterviewerRequest
from src.domain.interview.engine import AskFocus, AskIntro


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
