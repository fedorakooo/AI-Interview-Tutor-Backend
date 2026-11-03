import importlib
import logging
import pkgutil

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from shared_models.feature_flags.flags import feature_enabled
from src.api.errors.error_mapping import ERROR_MAPPING, INTERNAL_ERROR_SPEC, resolve_error_spec
from src.api.exception_handler import exception_container
from src.api.v1.router import router
from src.api.v1.schemas.interview_protocol import ErrorCode
from src.config import settings
from src.domain import exceptions
from src.domain.enums.cv_policy import CvPolicy
from src.domain.events.candidate_message import CandidateMessage
from src.domain.events.session_event import SessionEvent
from src.domain.exceptions.assessment_context_errors import AssessmentContextError
from src.domain.exceptions.feedback_errors import FeedbackError
from src.domain.exceptions.interview_service_error import InterviewServiceError
from src.domain.exceptions.report_errors import ReportError
from src.domain.exceptions.session_errors import EventSeqConflictError, SessionError
from src.domain.exceptions.spec_errors import SpecDraftError
from src.domain.value_objects.assessment_context import AssessmentContext

from tests.conftest import PUBLIC_KEY
from tests.fakes.builders import build_context
from tests.fakes.stack import FakeStack
from tests.fakes.tokens import mint_interview_token

EXCLUDED_BASES = {
    InterviewServiceError,
    AssessmentContextError,
    FeedbackError,
    ReportError,
    SessionError,
    SpecDraftError,
}


def _all_subclasses(cls: type[Exception]) -> set[type[Exception]]:
    found: set[type[Exception]] = set()
    for child in cls.__subclasses__():
        found.add(child)
        found |= _all_subclasses(child)
    return found


def _import_all_exception_modules() -> None:
    for module in pkgutil.iter_modules(exceptions.__path__, exceptions.__name__ + "."):
        importlib.import_module(module.name)


def test_every_service_error_is_mapped_or_excluded() -> None:
    _import_all_exception_modules()

    unmapped = {cls for cls in _all_subclasses(InterviewServiceError) if cls not in ERROR_MAPPING} - EXCLUDED_BASES

    assert not unmapped, f"Add an ERROR_MAPPING entry for: {sorted(cls.__name__ for cls in unmapped)}"


def test_event_seq_conflict_is_a_retryable_session_busy() -> None:
    spec = resolve_error_spec(EventSeqConflictError())

    assert (spec.http_status, spec.ws_code, spec.retryable) == (status.HTTP_409_CONFLICT, ErrorCode.SESSION_BUSY, True)


def test_unmapped_error_is_logged_and_becomes_internal_error(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR):
        spec = resolve_error_spec(SessionError())

    assert spec == INTERNAL_ERROR_SPEC
    assert "Unmapped error SessionError" in caplog.text


def test_http_handler_uses_the_mapping() -> None:
    app = FastAPI()
    exception_container(app)

    @app.get("/busy")
    async def busy() -> None:
        raise EventSeqConflictError()

    response = TestClient(app).get("/busy")

    assert (response.status_code, response.json()) == (409, {"detail": "Session is busy"})


@pytest.fixture
def context() -> AssessmentContext:
    return build_context(CvPolicy.REQUIRED)


def test_websocket_reports_a_seq_conflict_as_retryable_and_stays_open(
    context: AssessmentContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FEATURE_EMPLOYER_ASSESSMENT_DEMO", "true")
    monkeypatch.setattr(settings.jwt_settings, "public_key", PUBLIC_KEY)
    feature_enabled.cache_clear()
    stack = FakeStack(context=context)
    app = FastAPI()
    app.include_router(router)
    app.state.container = stack.container

    append = stack.event_repository.append

    async def append_or_conflict(event: SessionEvent) -> None:
        if isinstance(event, CandidateMessage):
            raise EventSeqConflictError()
        await append(event)

    monkeypatch.setattr(stack.event_repository, "append", append_or_conflict)
    try:
        with TestClient(app).websocket_connect("/api/v1/interview/ws") as websocket:
            websocket.send_json(
                {"type": "hello", "protocol_version": 1, "token": mint_interview_token(context.attempt_id)}
            )
            while websocket.receive_json()["type"] != "interviewer_message_completed":
                pass
            websocket.send_json(
                {"type": "candidate_message", "turn_id": "5f0c1c58-6c1e-4d4c-8c35-8d5f4f0a1b11", "text": "x"}
            )
            error = websocket.receive_json()
            websocket.send_json({"type": "ping"})
            pong = websocket.receive_json()
    finally:
        feature_enabled.cache_clear()

    assert (error["code"], error["retryable"], pong["type"]) == ("session_busy", True, "pong")
