from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect
from shared_models.assessment import AssessmentContext, CvPolicy, SessionPaused
from shared_models.assessment.mocks import mock_assessment_context
from shared_models.cv.cv_data import CVData
from shared_models.feature_flags.flags import feature_enabled
from src.api.interview.endpoints import router
from src.application.interview.session_service import InterviewSessionService
from src.config import settings
from src.domain.exceptions.assessment_context_errors import (
    AssessmentContextNotFoundError,
    AssessmentNotReadyError,
)
from src.domain.interfaces.assessment_context_client import IAssessmentContextClient

from tests.conftest import PUBLIC_KEY
from tests.unit_tests.fakes import (
    FakeCvProvider,
    InMemoryJournal,
    InMemoryLock,
    RecordingPublisher,
    ScriptedEvaluator,
    ScriptedInterviewer,
)
from tests.unit_tests.test_open_interview_connection_use_case import mint_interview_token

URL = "/api/v2/interview/ws"


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


@pytest.fixture(autouse=True)
def enabled_flag(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("FEATURE_EMPLOYER_ASSESSMENT_DEMO", "true")
    monkeypatch.setattr(settings.jwt_settings, "public_key", PUBLIC_KEY)
    feature_enabled.cache_clear()
    yield
    feature_enabled.cache_clear()


@pytest.fixture
def context() -> AssessmentContext:
    return mock_assessment_context(CvPolicy.REQUIRED)


class Backend:
    def __init__(self, context: AssessmentContext, error: Exception | None = None) -> None:
        self.context_client = FakeContextClient(context, error)
        self.journal = InMemoryJournal()
        self.publisher = RecordingPublisher()
        self.service = InterviewSessionService(
            journal=self.journal,
            lock=InMemoryLock(),
            evaluator=ScriptedEvaluator(),
            interviewer=ScriptedInterviewer(),
            cv_provider=FakeCvProvider(CVData()),
            completed_publisher=self.publisher,
        )

    def client(self) -> TestClient:
        app = FastAPI()
        app.include_router(router)
        app.state.assessment_context_client = self.context_client
        app.state.interview_session_service = self.service
        return TestClient(app)


def hello(token: str, **overrides: object) -> dict[str, object]:
    return {"type": "hello", "protocol_version": 1, "token": token} | overrides


def receive_until(websocket, message_type: str) -> list[dict]:
    received = []
    while True:
        message = websocket.receive_json()
        received.append(message)
        if message["type"] == message_type:
            return received


def test_hello_returns_ready_and_streams_the_first_question(context: AssessmentContext) -> None:
    backend = Backend(context)
    last_event_id = str(uuid4())

    with backend.client().websocket_connect(URL) as websocket:
        websocket.send_json(hello(mint_interview_token(context.attempt_id), last_event_id=last_event_id))
        ready = websocket.receive_json()
        first = receive_until(websocket, "interviewer_message_completed")

    assert ready["type"] == "ready"
    assert ready["attempt_id"] == str(context.attempt_id)
    assert ready["question_count"] == context.template.question_count
    assert ready["last_event_id"] == last_event_id
    assert [m["type"] for m in first] == [
        "interviewer_message_started",
        "interviewer_message_delta",
        "interviewer_message_delta",
        "interviewer_message_completed",
    ]
    assert first[-1]["text"] == "Question about databases please."
    assert backend.context_client.requested == [context.attempt_id]


def test_attempt_id_is_not_read_from_the_url(context: AssessmentContext) -> None:
    backend = Backend(context)

    with backend.client().websocket_connect(f"{URL}?attempt_id={uuid4()}") as websocket:
        websocket.send_json(hello(mint_interview_token(context.attempt_id)))
        receive_until(websocket, "interviewer_message_completed")

    assert backend.context_client.requested == [context.attempt_id]


def test_candidate_answer_gets_the_next_streamed_question(context: AssessmentContext) -> None:
    with Backend(context).client().websocket_connect(URL) as websocket:
        websocket.send_json(hello(mint_interview_token(context.attempt_id)))
        receive_until(websocket, "interviewer_message_completed")

        websocket.send_json({"type": "ping"})
        assert websocket.receive_json() == {"type": "pong"}

        turn_id = str(uuid4())
        websocket.send_json({"type": "candidate_message", "turn_id": turn_id, "text": "I would use EXPLAIN"})
        reply = receive_until(websocket, "interviewer_message_completed")
        assert reply[-1]["turn_id"] == turn_id

        websocket.send_text("not json")
        assert websocket.receive_json()["code"] == "invalid_message"


def test_disconnect_pauses_and_reconnect_replays_the_transcript(context: AssessmentContext) -> None:
    backend = Backend(context)
    token = mint_interview_token(context.attempt_id)

    with backend.client().websocket_connect(URL) as websocket:
        websocket.send_json(hello(token))
        receive_until(websocket, "interviewer_message_completed")
        websocket.send_json({"type": "candidate_message", "turn_id": str(uuid4()), "text": "my answer"})
        receive_until(websocket, "interviewer_message_completed")

    events = backend.journal.events[str(context.attempt_id)]
    assert isinstance(events[-1], SessionPaused)

    with backend.client().websocket_connect(URL) as websocket:
        websocket.send_json(hello(token))
        ready = websocket.receive_json()
        transcript = []
        while len(transcript) < 3:
            transcript.append(websocket.receive_json())

    assert ready["type"] == "ready"
    assert [(m["type"], m["role"]) for m in transcript] == [
        ("transcript_entry", "interviewer"),
        ("transcript_entry", "candidate"),
        ("transcript_entry", "interviewer"),
    ]
    assert transcript[1]["text"] == "my answer"


def test_reconnect_with_last_event_id_replays_only_newer_events(context: AssessmentContext) -> None:
    backend = Backend(context)
    token = mint_interview_token(context.attempt_id)
    with backend.client().websocket_connect(URL) as websocket:
        websocket.send_json(hello(token))
        first = receive_until(websocket, "interviewer_message_completed")[-1]
        websocket.send_json({"type": "candidate_message", "turn_id": str(uuid4()), "text": "my answer"})
        receive_until(websocket, "interviewer_message_completed")

    with backend.client().websocket_connect(URL) as websocket:
        websocket.send_json(hello(token, last_event_id=first["event_id"]))
        websocket.receive_json()
        replayed = [websocket.receive_json(), websocket.receive_json()]

    assert [m["role"] for m in replayed] == ["candidate", "interviewer"]


def expect_rejection(client: TestClient, first_message: dict[str, object] | str) -> tuple[str, int]:
    with client.websocket_connect(URL) as websocket:
        if isinstance(first_message, str):
            websocket.send_text(first_message)
        else:
            websocket.send_json(first_message)
        error = websocket.receive_json()
        with pytest.raises(WebSocketDisconnect) as closed:
            websocket.receive_json()
    return error["code"], closed.value.code


def test_invalid_token_is_rejected(context: AssessmentContext) -> None:
    backend = Backend(context)

    assert expect_rejection(backend.client(), hello("garbage")) == ("unauthorized", 1008)
    assert backend.context_client.requested == []


def test_unsupported_protocol_version_is_rejected(context: AssessmentContext) -> None:
    message = hello(mint_interview_token(context.attempt_id), protocol_version=99)

    assert expect_rejection(Backend(context).client(), message) == ("unsupported_protocol_version", 1008)


@pytest.mark.parametrize("first_message", ["not json", {"type": "ping"}])
def test_first_message_must_be_hello(context: AssessmentContext, first_message: dict[str, object] | str) -> None:
    assert expect_rejection(Backend(context).client(), first_message) == ("invalid_message", 1008)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (AssessmentNotReadyError(), ("assessment_not_ready", 1008)),
        (AssessmentContextNotFoundError(), ("assessment_unavailable", 1011)),
    ],
)
def test_context_failures_are_reported(context: AssessmentContext, error: Exception, expected: tuple[str, int]) -> None:
    client = Backend(context, error=error).client()

    assert expect_rejection(client, hello(mint_interview_token(context.attempt_id))) == expected


def test_missing_cv_for_a_required_policy_closes_the_connection(context: AssessmentContext) -> None:
    backend = Backend(context)
    backend.service._cv_provider = FakeCvProvider(None)

    with backend.client().websocket_connect(URL) as websocket:
        websocket.send_json(hello(mint_interview_token(context.attempt_id)))
        websocket.receive_json()
        assert websocket.receive_json()["code"] == "assessment_not_ready"
        with pytest.raises(WebSocketDisconnect):
            websocket.receive_json()


def test_missing_hello_times_out(context: AssessmentContext, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "interview_hello_timeout_seconds", 0.05)

    with Backend(context).client().websocket_connect(URL) as websocket:
        assert websocket.receive_json()["code"] == "invalid_message"


def test_endpoint_is_closed_when_feature_is_disabled(
    context: AssessmentContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FEATURE_EMPLOYER_ASSESSMENT_DEMO", "false")
    feature_enabled.cache_clear()

    with pytest.raises(WebSocketDisconnect):
        with Backend(context).client().websocket_connect(URL):
            pass
