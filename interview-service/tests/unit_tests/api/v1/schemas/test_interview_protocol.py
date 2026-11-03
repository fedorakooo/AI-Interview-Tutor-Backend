from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError
from src.api.v1.schemas.interview_protocol import (
    PROTOCOL_VERSION,
    ClientCandidateMessage,
    ClientHello,
    ClientMessageAdapter,
    ClientPing,
    ErrorCode,
    ServerError,
    ServerInterviewerMessageCompleted,
    ServerInterviewerMessageDelta,
    ServerInterviewerMessageStarted,
    ServerMessageAdapter,
    ServerPong,
    ServerReady,
    ServerSessionCompleted,
    ServerTranscriptEntry,
)


@pytest.mark.parametrize(
    "message",
    [
        ClientHello(protocol_version=PROTOCOL_VERSION, token="jwt", last_event_id=uuid4()),
        ClientCandidateMessage(turn_id=uuid4(), text="answer"),
        ClientPing(),
    ],
)
def test_client_messages_round_trip_through_the_union(message: object) -> None:
    raw = message.model_dump_json()

    assert ClientMessageAdapter.validate_json(raw) == message


@pytest.mark.parametrize(
    "raw",
    [
        "{}",
        '{"type": "unknown"}',
        '{"type": "hello", "protocol_version": 1}',
        '{"type": "candidate_message", "turn_id": "not-a-uuid", "text": "x"}',
        '{"type": "candidate_message", "turn_id": "9f1c2a4e-0b7d-4c1a-9a55-3d2f8e6b7c10", "text": ""}',
    ],
)
def test_invalid_client_messages_are_rejected(raw: str) -> None:
    with pytest.raises(ValidationError):
        ClientMessageAdapter.validate_json(raw)


def test_server_messages_round_trip_through_the_union() -> None:
    turn_id, message_id = uuid4(), uuid4()
    messages = [
        ServerReady(attempt_id=uuid4(), language="en", question_count=9, duration_minutes=45),
        ServerTranscriptEntry(
            event_id=uuid4(), seq=2, role="interviewer", text="Hi", occurred_at=datetime(2026, 11, 2, tzinfo=UTC)
        ),
        ServerInterviewerMessageStarted(turn_id=turn_id, message_id=message_id),
        ServerInterviewerMessageDelta(turn_id=turn_id, message_id=message_id, delta="Hel"),
        ServerInterviewerMessageCompleted(
            turn_id=turn_id, message_id=message_id, event_id=uuid4(), seq=3, text="Hello"
        ),
        ServerSessionCompleted(event_id=uuid4(), seq=20),
        ServerPong(),
        ServerError(code=ErrorCode.ENGINE_UNAVAILABLE, message="down", retryable=True),
    ]

    for message in messages:
        assert ServerMessageAdapter.validate_json(message.model_dump_json()) == message
