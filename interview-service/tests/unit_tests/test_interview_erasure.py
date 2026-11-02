from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.exception_handler import exception_container
from src.api.internal.router import router as internal_router
from src.config import settings
from src.infrastructure.mongo.repositories.attempt_data_repository import AttemptDataRepository

from tests.unit_tests.fakes import FakeStack

TOKEN = "internal-secret"


class FakeCollection:
    def __init__(self, documents: list[dict]) -> None:
        self.documents = documents

    async def delete_many(self, query: dict):
        key, value = next(iter(query.items()))
        before = len(self.documents)
        self.documents[:] = [d for d in self.documents if d.get(key) != value]

        class Result:
            deleted_count = before - len(self.documents)

        return Result()


def stores(attempt_id: str, other_id: str, correlation_id: str):
    return {
        "events": FakeCollection([{"session_id": attempt_id}, {"session_id": attempt_id}, {"session_id": other_id}]),
        "assessments": FakeCollection([{"attempt_id": attempt_id}, {"attempt_id": other_id}]),
        "reviews": FakeCollection([{"attempt_id": attempt_id}]),
        "feedback": FakeCollection([{"attempt_id": attempt_id}, {"attempt_id": attempt_id}]),
        "cv_documents": FakeCollection([{"correlation_id": correlation_id}, {"correlation_id": "other"}]),
    }


@pytest.mark.asyncio
async def test_eraser_deletes_only_the_records_of_one_attempt() -> None:
    attempt_id, other_id, correlation_id = uuid4(), uuid4(), uuid4()
    collections = stores(str(attempt_id), str(other_id), str(correlation_id))

    deleted = await AttemptDataRepository(**collections).erase(attempt_id, correlation_id)

    assert deleted == {"events": 2, "assessments": 1, "reviews": 1, "feedback": 2, "cv_documents": 1}
    assert collections["events"].documents == [{"session_id": str(other_id)}]
    assert collections["assessments"].documents == [{"attempt_id": str(other_id)}]
    assert collections["cv_documents"].documents == [{"correlation_id": "other"}]


@pytest.mark.asyncio
async def test_eraser_is_idempotent_and_skips_the_cv_when_there_is_none() -> None:
    attempt_id = uuid4()
    collections = stores(str(attempt_id), "x", "c")
    eraser = AttemptDataRepository(**collections)

    first = await eraser.erase(attempt_id, None)
    second = await eraser.erase(attempt_id, None)

    assert first["cv_documents"] == 0 and len(collections["cv_documents"].documents) == 2
    assert set(second.values()) == {0}


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
