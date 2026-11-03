from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.exception_handler import exception_container
from src.api.internal.router import router as internal_router
from src.config import settings
from src.domain.enums.cv_policy import CvPolicy
from src.domain.exceptions.assessment_context_errors import AssessmentContextNotFoundError, AssessmentNotReadyError

from tests.fakes.ai import ScriptedTextWriter
from tests.fakes.builders import build_context, build_events, build_template, build_texts
from tests.fakes.stack import FakeStack

POLICY = CvPolicy.REQUIRED
TEMPLATE = build_template(POLICY)
ATTEMPT_ID = build_context(POLICY).attempt_id
NOW = datetime(2026, 11, 3, tzinfo=UTC)
TOKEN = "internal-secret"


def stack(complete: bool = True, context_error: Exception | None = None) -> FakeStack:
    from dataclasses import replace

    fake = FakeStack(
        context=build_context(POLICY),
        context_error=context_error,
        now=NOW,
        text_writer=ScriptedTextWriter(build_texts(TEMPLATE)),
    )
    session_id = str(ATTEMPT_ID)
    source = build_events(POLICY) if complete else build_events(POLICY)[:-2]
    fake.event_repository.events[session_id] = [replace(event, session_id=session_id) for event in source]
    return fake


def api(fake: FakeStack) -> TestClient:
    app = FastAPI()
    app.include_router(internal_router)
    exception_container(app)
    app.state.container = fake.container
    return TestClient(app, headers={"X-Internal-Service-Token": TOKEN})


@pytest.fixture(autouse=True)
def internal_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "internal_service_token", TOKEN)


def test_internal_api_serves_overview_without_quotes_and_detail_with_them() -> None:
    client = api(stack())

    overview = client.get(f"/api/internal/reports/{ATTEMPT_ID}")
    detail = client.get(f"/api/internal/reports/{ATTEMPT_ID}/focus/databases")

    assert overview.status_code == 200 and '"quotes"' not in overview.text
    assert detail.status_code == 200 and detail.json()["timeline"][0]["evidence"]["quotes"]


def test_internal_api_review_round_trip() -> None:
    client = api(stack())

    response = client.post(
        f"/api/internal/reports/{ATTEMPT_ID}/focus/async_io/reviews",
        json={"author_id": str(uuid4()), "comment": "Looks fine", "manual_verdict": "adequate"},
    )

    assert response.status_code == 200
    assert response.json()["focus"]["final_verdict"] == "adequate"
    assert (
        client.post(
            f"/api/internal/reports/{ATTEMPT_ID}/focus/async_io/reviews", json={"author_id": "x", "comment": ""}
        ).status_code
        == 422
    )


@pytest.mark.parametrize("headers", [{}, {"X-Internal-Service-Token": "wrong"}])
def test_internal_api_requires_the_service_token(headers: dict[str, str]) -> None:
    client = api(stack())
    client.headers.pop("X-Internal-Service-Token")

    assert client.get(f"/api/internal/reports/{ATTEMPT_ID}", headers=headers).status_code == 401


def test_internal_api_is_disabled_without_a_configured_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "internal_service_token", "")

    assert api(stack()).get(f"/api/internal/reports/{ATTEMPT_ID}").status_code == 401


@pytest.mark.parametrize(
    ("error", "status_code"),
    [(AssessmentContextNotFoundError(), 404), (AssessmentNotReadyError(), 409)],
)
def test_internal_api_maps_context_errors(error: Exception, status_code: int) -> None:
    assert api(stack(context_error=error)).get(f"/api/internal/reports/{ATTEMPT_ID}").status_code == status_code


def test_internal_api_reports_unfinished_interviews_and_unknown_focus() -> None:
    assert api(stack(complete=False)).get(f"/api/internal/reports/{ATTEMPT_ID}").status_code == 409
    assert api(stack()).get(f"/api/internal/reports/{ATTEMPT_ID}/focus/unknown").status_code == 404


def test_internal_api_rejects_a_non_ascii_token_with_401_instead_of_failing() -> None:
    client = api(stack())

    response = client.get(
        f"/api/internal/reports/{ATTEMPT_ID}", headers={"X-Internal-Service-Token": "tökén".encode("latin-1")}
    )

    assert response.status_code == 401
