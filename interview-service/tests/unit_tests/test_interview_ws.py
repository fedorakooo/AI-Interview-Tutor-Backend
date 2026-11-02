from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect
from shared_models.assessment import AssessmentContext, CvPolicy
from shared_models.assessment.mocks import mock_assessment_context
from shared_models.feature_flags.flags import feature_enabled
from src.api.interview.endpoints import router
from src.config import settings
from src.domain.exceptions.assessment_context_errors import (
    AssessmentContextNotFoundError,
    AssessmentNotReadyError,
)
from src.domain.interfaces.assessment_context_client import IAssessmentContextClient

from tests.conftest import PUBLIC_KEY
from tests.unit_tests.test_open_interview_connection_use_case import mint_interview_token


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
    return mock_assessment_context(CvPolicy.NONE)


def make_client(context_client: FakeContextClient) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.assessment_context_client = context_client
    return TestClient(app)


def hello(token: str, **overrides: object) -> dict[str, object]:
    return {"type": "hello", "protocol_version": 1, "token": token} | overrides


def test_hello_with_valid_token_returns_ready(context: AssessmentContext) -> None:
    fake = FakeContextClient(context)
    last_event_id = str(uuid4())

    with make_client(fake).websocket_connect("/api/v2/interview/ws") as websocket:
        websocket.send_json(hello(mint_interview_token(context.attempt_id), last_event_id=last_event_id))
        ready = websocket.receive_json()

    assert ready["type"] == "ready"
    assert ready["attempt_id"] == str(context.attempt_id)
    assert ready["question_count"] == context.template.question_count
    assert ready["last_event_id"] == last_event_id
    assert fake.requested == [context.attempt_id]


def test_attempt_id_is_not_read_from_the_url(context: AssessmentContext) -> None:
    fake = FakeContextClient(context)

    with make_client(fake).websocket_connect(f"/api/v2/interview/ws?attempt_id={uuid4()}") as websocket:
        websocket.send_json(hello(mint_interview_token(context.attempt_id)))
        websocket.receive_json()

    assert fake.requested == [context.attempt_id]


def test_ping_and_unavailable_engine(context: AssessmentContext) -> None:
    with make_client(FakeContextClient(context)).websocket_connect("/api/v2/interview/ws") as websocket:
        websocket.send_json(hello(mint_interview_token(context.attempt_id)))
        websocket.receive_json()

        websocket.send_json({"type": "ping"})
        assert websocket.receive_json() == {"type": "pong"}

        websocket.send_json({"type": "candidate_message", "turn_id": str(uuid4()), "text": "hello"})
        assert websocket.receive_json()["code"] == "engine_unavailable"

        websocket.send_text("not json")
        assert websocket.receive_json()["code"] == "invalid_message"


def expect_rejection(client: TestClient, first_message: dict[str, object] | str) -> tuple[str, int]:
    with client.websocket_connect("/api/v2/interview/ws") as websocket:
        if isinstance(first_message, str):
            websocket.send_text(first_message)
        else:
            websocket.send_json(first_message)
        error = websocket.receive_json()
        with pytest.raises(WebSocketDisconnect) as closed:
            websocket.receive_json()
    return error["code"], closed.value.code


def test_invalid_token_is_rejected(context: AssessmentContext) -> None:
    fake = FakeContextClient(context)

    assert expect_rejection(make_client(fake), hello("garbage")) == ("unauthorized", 1008)
    assert fake.requested == []


def test_unsupported_protocol_version_is_rejected(context: AssessmentContext) -> None:
    message = hello(mint_interview_token(context.attempt_id), protocol_version=99)

    assert expect_rejection(make_client(FakeContextClient(context)), message) == ("unsupported_protocol_version", 1008)


@pytest.mark.parametrize("first_message", ["not json", {"type": "ping"}])
def test_first_message_must_be_hello(context: AssessmentContext, first_message: dict[str, object] | str) -> None:
    assert expect_rejection(make_client(FakeContextClient(context)), first_message) == ("invalid_message", 1008)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (AssessmentNotReadyError(), ("assessment_not_ready", 1008)),
        (AssessmentContextNotFoundError(), ("assessment_unavailable", 1011)),
    ],
)
def test_context_failures_are_reported(context: AssessmentContext, error: Exception, expected: tuple[str, int]) -> None:
    client = make_client(FakeContextClient(context, error=error))

    assert expect_rejection(client, hello(mint_interview_token(context.attempt_id))) == expected


def test_missing_hello_times_out(context: AssessmentContext, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "interview_hello_timeout_seconds", 0.05)

    with make_client(FakeContextClient(context)).websocket_connect("/api/v2/interview/ws") as websocket:
        assert websocket.receive_json()["code"] == "invalid_message"


def test_endpoint_is_closed_when_feature_is_disabled(
    context: AssessmentContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FEATURE_EMPLOYER_ASSESSMENT_DEMO", "false")
    feature_enabled.cache_clear()

    with pytest.raises(WebSocketDisconnect):
        with make_client(FakeContextClient(context)).websocket_connect("/api/v2/interview/ws"):
            pass
