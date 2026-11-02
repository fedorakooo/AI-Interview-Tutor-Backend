from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, TypeAdapter

PROTOCOL_VERSION = 1


class ErrorCode(StrEnum):
    INVALID_MESSAGE = "invalid_message"
    UNSUPPORTED_PROTOCOL_VERSION = "unsupported_protocol_version"
    UNAUTHORIZED = "unauthorized"
    ASSESSMENT_NOT_READY = "assessment_not_ready"
    ASSESSMENT_UNAVAILABLE = "assessment_unavailable"
    ENGINE_UNAVAILABLE = "engine_unavailable"
    INTERNAL_ERROR = "internal_error"


class ClientHello(BaseModel):
    type: Literal["hello"] = "hello"
    protocol_version: int
    token: str = Field(min_length=1, max_length=4096)
    last_event_id: UUID | None = None


class ClientCandidateMessage(BaseModel):
    type: Literal["candidate_message"] = "candidate_message"
    turn_id: UUID
    text: str = Field(min_length=1, max_length=8000)


class ClientPing(BaseModel):
    type: Literal["ping"] = "ping"


ClientMessage = Annotated[ClientHello | ClientCandidateMessage | ClientPing, Field(discriminator="type")]
ClientMessageAdapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)


class ServerReady(BaseModel):
    type: Literal["ready"] = "ready"
    protocol_version: int = PROTOCOL_VERSION
    attempt_id: UUID
    language: str
    question_count: int
    duration_minutes: int
    last_event_id: UUID | None = None


class ServerTranscriptEntry(BaseModel):
    type: Literal["transcript_entry"] = "transcript_entry"
    event_id: UUID
    seq: int
    role: Literal["interviewer", "candidate"]
    text: str
    occurred_at: datetime


class ServerInterviewerMessageStarted(BaseModel):
    type: Literal["interviewer_message_started"] = "interviewer_message_started"
    turn_id: UUID
    message_id: UUID


class ServerInterviewerMessageDelta(BaseModel):
    type: Literal["interviewer_message_delta"] = "interviewer_message_delta"
    turn_id: UUID
    message_id: UUID
    delta: str


class ServerInterviewerMessageCompleted(BaseModel):
    type: Literal["interviewer_message_completed"] = "interviewer_message_completed"
    turn_id: UUID
    message_id: UUID
    event_id: UUID
    seq: int
    text: str


class ServerSessionCompleted(BaseModel):
    type: Literal["session_completed"] = "session_completed"
    event_id: UUID
    seq: int


class ServerPong(BaseModel):
    type: Literal["pong"] = "pong"


class ServerError(BaseModel):
    type: Literal["error"] = "error"
    code: ErrorCode
    message: str
    retryable: bool = False


ServerMessage = Annotated[
    ServerReady
    | ServerTranscriptEntry
    | ServerInterviewerMessageStarted
    | ServerInterviewerMessageDelta
    | ServerInterviewerMessageCompleted
    | ServerSessionCompleted
    | ServerPong
    | ServerError,
    Field(discriminator="type"),
]
ServerMessageAdapter: TypeAdapter[ServerMessage] = TypeAdapter(ServerMessage)
