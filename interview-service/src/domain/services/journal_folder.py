from collections.abc import Sequence

from src.domain.entities.session_state import SessionState
from src.domain.enums.message_kind import MessageKind
from src.domain.enums.session_status import SessionStatus
from src.domain.events.candidate_message import CandidateMessage
from src.domain.events.evidence_recorded import EvidenceRecorded
from src.domain.events.focus_coverage_changed import FocusCoverageChanged
from src.domain.events.interviewer_message import InterviewerMessage
from src.domain.events.session_completed import SessionCompleted
from src.domain.events.session_event import SessionEvent
from src.domain.events.session_failed import SessionFailed
from src.domain.events.session_paused import SessionPaused
from src.domain.events.session_started import SessionStarted
from src.domain.exceptions.session_errors import InconsistentJournalError
from src.domain.services.evidence_verifier import EvidenceVerifier
from src.domain.value_objects.focus_coverage import FocusCoverage
from src.domain.value_objects.message_record import MessageRecord


class JournalFolder:
    @staticmethod
    def fold(events: Sequence[SessionEvent]) -> SessionState:
        if not events:
            raise InconsistentJournalError("Event log is empty")
        first = events[0]
        if not isinstance(first, SessionStarted):
            raise InconsistentJournalError("Event log must start with SessionStarted")

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
            JournalFolder._apply(state, event)
        return state

    @staticmethod
    def _apply(state: SessionState, event: SessionEvent) -> None:
        if state.status in (SessionStatus.COMPLETED, SessionStatus.FAILED):
            raise InconsistentJournalError("No events are allowed after a terminal event")
        if event.session_id != state.session_id:
            raise InconsistentJournalError("Event belongs to a different session")
        if event.seq <= state.last_seq:
            raise InconsistentJournalError(f"seq must increase monotonically, got {event.seq} after {state.last_seq}")
        if isinstance(event, SessionStarted):
            raise InconsistentJournalError("SessionStarted may appear only once")

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
            EvidenceVerifier.verify_evidence(event.evidence, state.messages)
            state.evidence.append(event.evidence)
        elif isinstance(event, FocusCoverageChanged):
            state.coverage[event.focus_id] = FocusCoverage(
                focus_id=event.focus_id,
                status=event.status,
                evidence_count=event.evidence_count,
                covered_must_cover=tuple(event.covered_must_cover),
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
