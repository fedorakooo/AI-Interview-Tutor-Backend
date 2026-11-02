from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from shared_models.assessment.evidence import EvidenceItem, QuoteRef
from shared_models.assessment.session_events import (
    CandidateMessage,
    CompletionReason,
    CoverageStatus,
    EvidenceRecorded,
    FocusCoverageChanged,
    InterviewerMessage,
    MessageKind,
    SessionCompleted,
    SessionEvent,
    SessionFailed,
    SessionPaused,
    SessionStarted,
)


class SessionStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class InvalidEventLogError(ValueError):
    """Raised when the event journal violates an ordering, reference or quote rule."""


class MessageRecord(BaseModel):
    seq: int
    role: Literal["interviewer", "candidate"]
    text: str
    kind: MessageKind | None = None
    focus_id: str | None = None
    custom_question_index: int | None = None


class FocusCoverage(BaseModel):
    focus_id: str
    status: CoverageStatus = CoverageStatus.NOT_STARTED
    evidence_count: int = 0
    covered_must_cover: list[str] = Field(default_factory=list)


class SessionState(BaseModel):
    session_id: str
    attempt_id: UUID
    template_version: int
    cv_attached: bool
    status: SessionStatus = SessionStatus.IN_PROGRESS
    started_at: datetime
    last_seq: int
    last_event_id: UUID
    messages: dict[int, MessageRecord] = Field(default_factory=dict)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    coverage: dict[str, FocusCoverage] = Field(default_factory=dict)
    questions_asked: int = 0
    completion_reason: CompletionReason | None = None
    failure_code: str | None = None
    paused_at: datetime | None = None
    paused_seconds: float = 0.0

    def active_elapsed(self, now: datetime) -> timedelta:
        """Return the time since the start, excluding every pause."""
        paused = self.paused_seconds
        if self.paused_at is not None:
            paused += (now - self.paused_at).total_seconds()
        return max(timedelta(), now - self.started_at - timedelta(seconds=paused))


def verify_quote(quote: QuoteRef, messages: Mapping[int, MessageRecord]) -> None:
    message = messages.get(quote.event_seq)
    if message is None or message.role != "candidate":
        raise InvalidEventLogError(f"Quote references seq {quote.event_seq}, which is not a candidate message")
    if message.text[quote.start : quote.end] != quote.text:
        raise InvalidEventLogError(f"Quote at seq {quote.event_seq} does not match the message text")


def verify_evidence(evidence: EvidenceItem, messages: Mapping[int, MessageRecord]) -> None:
    question = messages.get(evidence.question_seq)
    answer = messages.get(evidence.answer_seq)
    if question is None or question.role != "interviewer":
        raise InvalidEventLogError(f"Evidence question_seq {evidence.question_seq} is not an interviewer message")
    if answer is None or answer.role != "candidate":
        raise InvalidEventLogError(f"Evidence answer_seq {evidence.answer_seq} is not a candidate message")
    for quote in evidence.quotes:
        verify_quote(quote, messages)


def fold_events(events: Sequence[SessionEvent]) -> SessionState:
    """Fold the event journal into the current session state."""
    if not events:
        raise InvalidEventLogError("Event log is empty")
    first = events[0]
    if not isinstance(first, SessionStarted):
        raise InvalidEventLogError("Event log must start with SessionStarted")

    state = SessionState(
        session_id=first.session_id,
        attempt_id=first.attempt_id,
        template_version=first.template_version,
        cv_attached=first.cv_attached,
        started_at=first.occurred_at,
        last_seq=first.seq,
        last_event_id=first.event_id,
    )
    for event in events[1:]:
        _apply(state, event)
    return state


def _apply(state: SessionState, event: SessionEvent) -> None:
    if state.status in (SessionStatus.COMPLETED, SessionStatus.FAILED):
        raise InvalidEventLogError("No events are allowed after a terminal event")
    if event.session_id != state.session_id:
        raise InvalidEventLogError("Event belongs to a different session")
    if event.seq <= state.last_seq:
        raise InvalidEventLogError(f"seq must increase monotonically, got {event.seq} after {state.last_seq}")
    if isinstance(event, SessionStarted):
        raise InvalidEventLogError("SessionStarted may appear only once")

    if state.status == SessionStatus.PAUSED:
        state.status = SessionStatus.IN_PROGRESS
        if state.paused_at is not None:
            state.paused_seconds += (event.occurred_at - state.paused_at).total_seconds()
            state.paused_at = None
    state.last_seq = event.seq
    state.last_event_id = event.event_id

    if isinstance(event, InterviewerMessage):
        state.messages[event.seq] = MessageRecord(
            seq=event.seq,
            role="interviewer",
            text=event.text,
            kind=event.kind,
            focus_id=event.focus_id,
            custom_question_index=event.custom_question_index,
        )
        if event.kind in (MessageKind.QUESTION, MessageKind.FOLLOW_UP):
            state.questions_asked += 1
    elif isinstance(event, CandidateMessage):
        state.messages[event.seq] = MessageRecord(seq=event.seq, role="candidate", text=event.text)
    elif isinstance(event, EvidenceRecorded):
        verify_evidence(event.evidence, state.messages)
        state.evidence.append(event.evidence)
    elif isinstance(event, FocusCoverageChanged):
        state.coverage[event.focus_id] = FocusCoverage(
            focus_id=event.focus_id,
            status=event.status,
            evidence_count=event.evidence_count,
            covered_must_cover=list(event.covered_must_cover),
        )
    elif isinstance(event, SessionPaused):
        state.status = SessionStatus.PAUSED
        state.paused_at = event.occurred_at
    elif isinstance(event, SessionCompleted):
        state.status = SessionStatus.COMPLETED
        state.completion_reason = event.reason
    elif isinstance(event, SessionFailed):
        state.status = SessionStatus.FAILED
        state.failure_code = event.error_code
