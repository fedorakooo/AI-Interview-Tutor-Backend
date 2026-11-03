from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.exception_handler import exception_container
from src.api.internal.router import router as internal_router
from src.config import settings
from src.domain.enums.cv_policy import CvPolicy

from tests.fakes.ai import ScriptedFeedbackWriter, ScriptedTextWriter
from tests.fakes.builders import build_context, build_template, build_texts
from tests.fakes.stack import FakeStack, completed_stack

POLICY = CvPolicy.REQUIRED
TEMPLATE = build_template(POLICY)
ATTEMPT_ID = build_context(POLICY).attempt_id
NOW = datetime(2026, 11, 3, tzinfo=UTC)
FLAG = TEMPLATE.red_flags[1]
TOKEN = "internal-secret"


def stack_for(template=TEMPLATE) -> FakeStack:
    return completed_stack(
        context=replace(build_context(POLICY), template=template),
        now=NOW,
        text_writer=ScriptedTextWriter(build_texts(TEMPLATE)),
        feedback_writer=ScriptedFeedbackWriter(),
    )


def api(stack: FakeStack) -> TestClient:
    app = FastAPI()
    app.include_router(internal_router)
    exception_container(app)
    app.state.container = stack.container
    return TestClient(app, headers={"X-Internal-Service-Token": TOKEN})


@pytest.fixture(autouse=True)
def internal_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "internal_service_token", TOKEN)


def test_internal_api_returns_and_edits_feedback() -> None:
    client = api(stack_for())

    first = client.get(f"/api/internal/feedback/{ATTEMPT_ID}")
    edited = client.put(f"/api/internal/feedback/{ATTEMPT_ID}", json={"editor_id": str(uuid4()), "text": "Well done!"})

    assert first.status_code == 200 and first.json()["version"] == 1
    assert edited.status_code == 200 and edited.json()["version"] == 2 and edited.json()["text"] == "Well done!"


def test_internal_api_rejects_leaks_unfinished_interviews_and_missing_tokens() -> None:
    stack = stack_for()
    client = api(stack)

    leak = client.put(f"/api/internal/feedback/{ATTEMPT_ID}", json={"editor_id": str(uuid4()), "text": f"Flag: {FLAG}"})
    assert leak.status_code == 422

    stack.event_repository.events.clear()
    assert client.get(f"/api/internal/feedback/{ATTEMPT_ID}").status_code == 409

    client.headers.pop("X-Internal-Service-Token")
    assert client.get(f"/api/internal/feedback/{ATTEMPT_ID}").status_code == 401


def test_internal_api_hides_feedback_when_the_template_disables_it() -> None:
    client = api(stack_for(replace(TEMPLATE, candidate_feedback=False)))

    assert client.get(f"/api/internal/feedback/{ATTEMPT_ID}").status_code == 404
