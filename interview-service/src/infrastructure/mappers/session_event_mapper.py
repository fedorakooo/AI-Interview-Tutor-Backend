from typing import Any

from shared_models.assessment import session_events as contract

from src.domain.enums.completion_reason import CompletionReason
from src.domain.enums.coverage_status import CoverageStatus
from src.domain.enums.message_kind import MessageKind
from src.domain.enums.pause_reason import PauseReason
from src.domain.events.candidate_message import CandidateMessage
from src.domain.events.evidence_recorded import EvidenceRecorded
from src.domain.events.focus_coverage_changed import FocusCoverageChanged
from src.domain.events.interviewer_message import InterviewerMessage
from src.domain.events.session_completed import SessionCompleted
from src.domain.events.session_event import SessionEvent
from src.domain.events.session_failed import SessionFailed
from src.domain.events.session_paused import SessionPaused
from src.domain.events.session_started import SessionStarted
from src.infrastructure.mappers.evidence_mapper import EvidenceMapper


class SessionEventMapper:
    @staticmethod
    def to_document(event: SessionEvent) -> dict[str, Any]:
        return SessionEventMapper.to_contract(event).model_dump(mode="json")

    @staticmethod
    def from_document(document: dict[str, Any]) -> SessionEvent:
        return SessionEventMapper.to_domain(contract.SessionEventAdapter.validate_python(document))

    @staticmethod
    def to_contract(event: SessionEvent) -> Any:
        base = {
            "event_id": event.event_id,
            "session_id": event.session_id,
            "seq": event.seq,
            "occurred_at": event.occurred_at,
        }
        if isinstance(event, SessionStarted):
            return contract.SessionStarted(
                **base,
                attempt_id=event.attempt_id,
                template_version=event.template_version,
                cv_attached=event.cv_attached,
            )
        if isinstance(event, InterviewerMessage):
            return contract.InterviewerMessage(
                **base,
                turn_id=event.turn_id,
                kind=contract.MessageKind(event.kind.value),
                text=event.text,
                focus_id=event.focus_id,
                custom_question_index=event.custom_question_index,
            )
        if isinstance(event, CandidateMessage):
            return contract.CandidateMessage(**base, turn_id=event.turn_id, text=event.text)
        if isinstance(event, EvidenceRecorded):
            return contract.EvidenceRecorded(**base, evidence=EvidenceMapper.to_contract(event.evidence))
        if isinstance(event, FocusCoverageChanged):
            return contract.FocusCoverageChanged(
                **base,
                focus_id=event.focus_id,
                status=contract.CoverageStatus(event.status.value),
                evidence_count=event.evidence_count,
                covered_must_cover=list(event.covered_must_cover),
            )
        if isinstance(event, SessionPaused):
            return contract.SessionPaused(**base, reason=contract.PauseReason(event.reason.value))
        if isinstance(event, SessionCompleted):
            return contract.SessionCompleted(**base, reason=contract.CompletionReason(event.reason.value))
        return contract.SessionFailed(**base, error_code=event.error_code)

    @staticmethod
    def to_domain(event: Any) -> SessionEvent:
        base = {
            "event_id": event.event_id,
            "session_id": event.session_id,
            "seq": event.seq,
            "occurred_at": event.occurred_at,
        }
        if isinstance(event, contract.SessionStarted):
            return SessionStarted(
                **base,
                attempt_id=event.attempt_id,
                template_version=event.template_version,
                cv_attached=event.cv_attached,
            )
        if isinstance(event, contract.InterviewerMessage):
            return InterviewerMessage(
                **base,
                turn_id=event.turn_id,
                kind=MessageKind(event.kind.value),
                text=event.text,
                focus_id=event.focus_id,
                custom_question_index=event.custom_question_index,
            )
        if isinstance(event, contract.CandidateMessage):
            return CandidateMessage(**base, turn_id=event.turn_id, text=event.text)
        if isinstance(event, contract.EvidenceRecorded):
            return EvidenceRecorded(**base, evidence=EvidenceMapper.to_domain(event.evidence))
        if isinstance(event, contract.FocusCoverageChanged):
            return FocusCoverageChanged(
                **base,
                focus_id=event.focus_id,
                status=CoverageStatus(event.status.value),
                evidence_count=event.evidence_count,
                covered_must_cover=tuple(event.covered_must_cover),
            )
        if isinstance(event, contract.SessionPaused):
            return SessionPaused(**base, reason=PauseReason(event.reason.value))
        if isinstance(event, contract.SessionCompleted):
            return SessionCompleted(**base, reason=CompletionReason(event.reason.value))
        return SessionFailed(**base, error_code=event.error_code)
