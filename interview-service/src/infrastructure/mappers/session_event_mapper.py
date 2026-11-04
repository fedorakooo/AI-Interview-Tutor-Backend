from typing import Any

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
from src.infrastructure.mongo.documents import session_event_document as document_model


class SessionEventMapper:
    @staticmethod
    def to_document(event: SessionEvent) -> dict[str, Any]:
        return SessionEventMapper.to_model(event).model_dump(mode="json")

    @staticmethod
    def from_document(document: dict[str, Any]) -> SessionEvent:
        return SessionEventMapper.to_domain(document_model.SessionEventAdapter.validate_python(document))

    @staticmethod
    def to_model(event: SessionEvent) -> Any:
        base = {
            "event_id": event.event_id,
            "session_id": event.session_id,
            "seq": event.seq,
            "occurred_at": event.occurred_at,
        }
        if isinstance(event, SessionStarted):
            return document_model.SessionStartedDocument(
                **base,
                attempt_id=event.attempt_id,
                template_version=event.template_version,
                cv_attached=event.cv_attached,
            )
        if isinstance(event, InterviewerMessage):
            return document_model.InterviewerMessageDocument(
                **base,
                turn_id=event.turn_id,
                kind=document_model.MessageKind(event.kind.value),
                text=event.text,
                focus_id=event.focus_id,
                custom_question_index=event.custom_question_index,
            )
        if isinstance(event, CandidateMessage):
            return document_model.CandidateMessageDocument(**base, turn_id=event.turn_id, text=event.text)
        if isinstance(event, EvidenceRecorded):
            return document_model.EvidenceRecordedDocument(**base, evidence=EvidenceMapper.to_model(event.evidence))
        if isinstance(event, FocusCoverageChanged):
            return document_model.FocusCoverageChangedDocument(
                **base,
                focus_id=event.focus_id,
                status=document_model.CoverageStatus(event.status.value),
                evidence_count=event.evidence_count,
                covered_must_cover=list(event.covered_must_cover),
            )
        if isinstance(event, SessionPaused):
            return document_model.SessionPausedDocument(**base, reason=document_model.PauseReason(event.reason.value))
        if isinstance(event, SessionCompleted):
            return document_model.SessionCompletedDocument(
                **base, reason=document_model.CompletionReason(event.reason.value)
            )
        return document_model.SessionFailedDocument(**base, error_code=event.error_code)

    @staticmethod
    def to_domain(event: Any) -> SessionEvent:
        base = {
            "event_id": event.event_id,
            "session_id": event.session_id,
            "seq": event.seq,
            "occurred_at": event.occurred_at,
        }
        if isinstance(event, document_model.SessionStartedDocument):
            return SessionStarted(
                **base,
                attempt_id=event.attempt_id,
                template_version=event.template_version,
                cv_attached=event.cv_attached,
            )
        if isinstance(event, document_model.InterviewerMessageDocument):
            return InterviewerMessage(
                **base,
                turn_id=event.turn_id,
                kind=MessageKind(event.kind.value),
                text=event.text,
                focus_id=event.focus_id,
                custom_question_index=event.custom_question_index,
            )
        if isinstance(event, document_model.CandidateMessageDocument):
            return CandidateMessage(**base, turn_id=event.turn_id, text=event.text)
        if isinstance(event, document_model.EvidenceRecordedDocument):
            return EvidenceRecorded(**base, evidence=EvidenceMapper.to_domain(event.evidence))
        if isinstance(event, document_model.FocusCoverageChangedDocument):
            return FocusCoverageChanged(
                **base,
                focus_id=event.focus_id,
                status=CoverageStatus(event.status.value),
                evidence_count=event.evidence_count,
                covered_must_cover=tuple(event.covered_must_cover),
            )
        if isinstance(event, document_model.SessionPausedDocument):
            return SessionPaused(**base, reason=PauseReason(event.reason.value))
        if isinstance(event, document_model.SessionCompletedDocument):
            return SessionCompleted(**base, reason=CompletionReason(event.reason.value))
        return SessionFailed(**base, error_code=event.error_code)
