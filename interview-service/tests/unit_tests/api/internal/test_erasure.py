from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.exception_handler import exception_container
from src.api.internal.router import router as internal_router
from src.config import settings
from src.infrastructure.mongo.repositories.attempt_data_repository import AttemptDataRepository

from tests.fakes.stack import FakeStack
from tests.unit_tests.infrastructure.mongo.test_attempt_data_repository import stores

TOKEN = "internal-secret"


def api(stack: FakeStack) -> TestClient:
    app = FastAPI()
    app.include_router(internal_router)
    exception_container(app)
    app.state.container = stack.container
    return TestClient(app, headers={"X-Internal-Service-Token": TOKEN})


@pytest.fixture(autouse=True)
def internal_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "internal_service_token", TOKEN)


def test_internal_api_erases_under_the_session_lock_and_requires_the_token() -> None:
    attempt_id = uuid4()
    collections = stores(str(attempt_id), "x", "c")
    stack = FakeStack(attempt_data_repository=AttemptDataRepository(**collections))
    lock = stack.lock
    client = api(stack)

    response = client.post(f"/api/internal/erasure/{attempt_id}", json={"cv_correlation_id": None})

    assert response.status_code == 200
    assert response.json() == {
        "attempt_id": str(attempt_id),
        "deleted": {"events": 2, "assessments": 1, "reviews": 1, "feedback": 2, "cv_documents": 0},
    }
    assert lock.held == set()
    client.headers.pop("X-Internal-Service-Token")
    assert client.post(f"/api/internal/erasure/{attempt_id}", json={}).status_code == 401


def test_a_running_interview_is_not_erased() -> None:
    attempt_id = uuid4()
    stack = FakeStack(attempt_data_repository=AttemptDataRepository(**stores(str(attempt_id), "x", "c")))
    stack.lock.held.add(str(attempt_id))
    client = api(stack)

    assert client.post(f"/api/internal/erasure/{attempt_id}", json={}).status_code == 409
