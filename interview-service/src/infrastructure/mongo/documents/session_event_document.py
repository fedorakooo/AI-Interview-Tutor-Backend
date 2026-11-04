from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, TypeAdapter, model_validator

from src.infrastructure.mongo.documents.evidence_document import EvidenceDocument


class MessageKind(StrEnum):
    INTRO = "intro"
    QUESTION = "question"
    FOLLOW_UP = "follow_up"
    CLOSING = "closing"


class CoverageStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COVERED = "covered"
    EXHAUSTED = "exhausted"


class PauseReason(StrEnum):
    DISCONNECT = "disconnect"
    INACTIVITY = "inactivity"
    CANDIDATE_REQUEST = "candidate_request"


class CompletionReason(StrEnum):
    ALL_COVERED = "all_covered"
    QUESTION_BUDGET = "question_budget"
    TIME_BUDGET = "time_budget"
    CANDIDATE_ENDED = "candidate_ended"


class SessionEventBaseDocument(BaseModel):
    event_id: UUID
    session_id: str = Field(min_length=1, max_length=128)
    seq: int = Field(ge=1)
    occurred_at: datetime


class SessionStartedDocument(SessionEventBaseDocument):
    type: Literal["session_started"] = "session_started"
    attempt_id: UUID
    template_version: int = Field(ge=1)
    cv_attached: bool


class InterviewerMessageDocument(SessionEventBaseDocument):
    type: Literal["interviewer_message"] = "interviewer_message"
    turn_id: UUID
    kind: MessageKind
    text: str = Field(min_length=1, max_length=4000)
    focus_id: str | None = Field(default=None, max_length=64)
    custom_question_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def question_targets_focus(self) -> "InterviewerMessageDocument":
        asks = self.kind in (MessageKind.QUESTION, MessageKind.FOLLOW_UP)
        if asks and self.focus_id is None:
            raise ValueError("Questions must target a focus area")
        if not asks and (self.focus_id is not None or self.custom_question_index is not None):
            raise ValueError("Only questions may reference a focus area")
        return self


class CandidateMessageDocument(SessionEventBaseDocument):
    type: Literal["candidate_message"] = "candidate_message"
    turn_id: UUID
    text: str = Field(min_length=1, max_length=8000)


class EvidenceRecordedDocument(SessionEventBaseDocument):
    type: Literal["evidence_recorded"] = "evidence_recorded"
    evidence: EvidenceDocument


class FocusCoverageChangedDocument(SessionEventBaseDocument):
    type: Literal["focus_coverage_changed"] = "focus_coverage_changed"
    focus_id: str = Field(min_length=1, max_length=64)
    status: CoverageStatus
    evidence_count: int = Field(ge=0)
    covered_must_cover: list[str] = Field(default_factory=list)


class SessionPausedDocument(SessionEventBaseDocument):
    type: Literal["session_paused"] = "session_paused"
    reason: PauseReason


class SessionCompletedDocument(SessionEventBaseDocument):
    type: Literal["session_completed"] = "session_completed"
    reason: CompletionReason


class SessionFailedDocument(SessionEventBaseDocument):
    type: Literal["session_failed"] = "session_failed"
    error_code: str = Field(min_length=1, max_length=64)


SessionEventDocument = Annotated[
    SessionStartedDocument
    | InterviewerMessageDocument
    | CandidateMessageDocument
    | EvidenceRecordedDocument
    | FocusCoverageChangedDocument
    | SessionPausedDocument
    | SessionCompletedDocument
    | SessionFailedDocument,
    Field(discriminator="type"),
]

SessionEventAdapter: TypeAdapter[SessionEventDocument] = TypeAdapter(SessionEventDocument)
