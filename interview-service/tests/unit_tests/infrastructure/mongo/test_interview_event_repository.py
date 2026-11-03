from dataclasses import replace

import pytest
from pymongo.errors import DuplicateKeyError, PyMongoError
from src.domain.enums.cv_policy import CvPolicy
from src.domain.exceptions.dependency_errors import DependencyUnavailableError
from src.domain.exceptions.session_errors import EventSeqConflictError
from src.infrastructure.mongo.repositories.interview_event_repository import InterviewEventRepository

from tests.fakes.builders import build_events


class FakeCursor:
    def __init__(self, documents: list[dict]) -> None:
        self.documents = documents

    def sort(self, key: str, direction: int) -> "FakeCursor":
        self.documents = sorted(self.documents, key=lambda document: document[key], reverse=direction < 0)
        return self

    async def to_list(self, length: int | None) -> list[dict]:
        return self.documents


class FakeCollection:
    def __init__(self) -> None:
        self.documents: list[dict] = []
        self.indexes: list[tuple] = []

    async def create_index(self, keys, **kwargs) -> None:
        self.indexes.append((keys, kwargs))

    async def insert_one(self, document: dict) -> None:
        if any(d["session_id"] == document["session_id"] and d["seq"] == document["seq"] for d in self.documents):
            raise DuplicateKeyError("duplicate")
        self.documents.append(dict(document))

    def find(self, query: dict, projection: dict) -> FakeCursor:
        hidden = {key for key, value in projection.items() if value == 0}
        matched = [d for d in self.documents if d["session_id"] == query["session_id"]]
        return FakeCursor([{k: v for k, v in d.items() if k not in hidden} for d in matched])


class BrokenCollection:
    async def insert_one(self, document: dict) -> None:
        raise PyMongoError("down")


async def test_journal_round_trips_events_in_sequence_order() -> None:
    journal = InterviewEventRepository(FakeCollection())
    events = build_events(CvPolicy.NONE)

    for event in reversed(events):
        await journal.append(event)

    assert await journal.list_events(events[0].session_id) == events


async def test_journal_rejects_a_duplicate_sequence_number() -> None:
    journal = InterviewEventRepository(FakeCollection())
    event = build_events(CvPolicy.REQUIRED)[0]
    await journal.append(event)

    with pytest.raises(EventSeqConflictError):
        await journal.append(replace(event, event_id=event.event_id))


async def test_journal_creates_unique_indexes() -> None:
    collection = FakeCollection()

    await InterviewEventRepository(collection).ensure_indexes()

    assert all(kwargs == {"unique": True} for _, kwargs in collection.indexes)
    assert len(collection.indexes) == 2


async def test_storage_failure_becomes_a_dependency_error() -> None:
    with pytest.raises(DependencyUnavailableError):
        await InterviewEventRepository(BrokenCollection()).append(build_events(CvPolicy.REQUIRED)[0])
