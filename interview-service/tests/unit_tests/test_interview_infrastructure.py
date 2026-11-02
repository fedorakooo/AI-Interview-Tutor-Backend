from uuid import uuid4

import pytest
from pymongo.errors import DuplicateKeyError
from shared_models.assessment import CvPolicy
from shared_models.assessment.mocks import mock_session_events
from src.domain.exceptions.session_errors import EventSeqConflictError, SessionBusyError
from src.infrastructure.mongo_candidate_cv_provider import MongoCandidateCvProvider
from src.infrastructure.mongo_event_journal import MongoEventJournal
from src.infrastructure.redis.session_lock import RedisSessionLock


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


async def test_journal_round_trips_events_in_sequence_order() -> None:
    journal = MongoEventJournal(FakeCollection())
    events = mock_session_events(CvPolicy.NONE)

    for event in reversed(events):
        await journal.append(event)

    assert await journal.list_events(events[0].session_id) == events


async def test_journal_rejects_a_duplicate_sequence_number() -> None:
    journal = MongoEventJournal(FakeCollection())
    event = mock_session_events(CvPolicy.REQUIRED)[0]
    await journal.append(event)

    with pytest.raises(EventSeqConflictError):
        await journal.append(event)


async def test_journal_creates_unique_indexes() -> None:
    collection = FakeCollection()

    await MongoEventJournal(collection).ensure_indexes()

    assert all(kwargs == {"unique": True} for _, kwargs in collection.indexes)
    assert len(collection.indexes) == 2


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(self, key: str, value: str, nx: bool, px: int) -> bool:
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def eval(self, script: str, numkeys: int, key: str, token: str) -> int:
        if self.values.get(key) == token:
            del self.values[key]
            return 1
        return 0


async def test_lock_is_exclusive_and_released() -> None:
    redis = FakeRedis()
    lock = RedisSessionLock(redis, wait_seconds=0.05)

    async with lock.hold("session-1"):
        with pytest.raises(SessionBusyError):
            async with lock.hold("session-1"):
                pass
        async with lock.hold("session-2"):
            pass

    async with lock.hold("session-1"):
        pass
    assert redis.values == {}


async def test_lock_is_released_when_the_body_fails() -> None:
    redis = FakeRedis()
    lock = RedisSessionLock(redis, wait_seconds=0.05)

    with pytest.raises(RuntimeError):
        async with lock.hold("session-1"):
            raise RuntimeError("boom")

    assert redis.values == {}


class FakeMongoRepository:
    def __init__(self, document: dict | None) -> None:
        self.document = document
        self.queries: list[tuple] = []

    async def find_latest_by_field(self, field_name: str, field_value: str, extra_filter: dict | None = None):
        self.queries.append((field_name, field_value, extra_filter))
        return self.document


async def test_cv_provider_strips_metadata_and_looks_up_by_correlation_id() -> None:
    from uuid import uuid4

    correlation_id = uuid4()
    repository = FakeMongoRepository(
        {
            "_id": "x",
            "correlation_id": str(correlation_id),
            "user_id": "u",
            "status": "completed",
            "specialization": "Backend",
        }
    )

    cv = await MongoCandidateCvProvider(repository).get(correlation_id)

    assert cv is not None and cv.specialization == "Backend"
    assert repository.queries == [("correlation_id", str(correlation_id), {"status": "completed"})]


async def test_cv_provider_returns_nothing_for_a_missing_document() -> None:
    from uuid import uuid4

    assert await MongoCandidateCvProvider(FakeMongoRepository(None)).get(uuid4()) is None


class FakeDocumentCollection:
    def __init__(self) -> None:
        self.documents: list[dict] = []

    async def create_index(self, keys, **kwargs) -> None:
        return None

    async def insert_one(self, document: dict) -> None:
        if any(d.get("attempt_id") == document.get("attempt_id") and "assessment_id" in d for d in self.documents):
            raise DuplicateKeyError("duplicate")
        self.documents.append(dict(document))

    async def find_one(self, query: dict, projection: dict) -> dict | None:
        return next((d for d in self.documents if d["attempt_id"] == query["attempt_id"]), None)

    def find(self, query: dict, projection: dict) -> FakeCursor:
        return FakeCursor([d for d in self.documents if d["attempt_id"] == query["attempt_id"]])


async def test_assessment_store_round_trips_a_report_without_reviews_and_keeps_the_first_save() -> None:
    from shared_models.assessment.mocks import mock_assessment
    from src.infrastructure.mongo_assessment_store import MongoAssessmentStore

    store = MongoAssessmentStore(FakeDocumentCollection(), FakeDocumentCollection())
    assessment = mock_assessment()

    await store.save(assessment)
    await store.save(assessment.model_copy(update={"overall_summary": "A later duplicate"}))

    assert await store.get(assessment.attempt_id) == assessment
    assert await store.get(uuid4()) is None


async def test_assessment_store_appends_reviews_in_creation_order() -> None:
    from datetime import UTC, datetime

    from shared_models.assessment import ReviewEntry
    from src.infrastructure.mongo_assessment_store import MongoAssessmentStore

    store = MongoAssessmentStore(FakeDocumentCollection(), FakeDocumentCollection())
    attempt_id = uuid4()
    for minute, comment in enumerate(["first", "second"]):
        await store.add_review(
            attempt_id,
            "databases",
            ReviewEntry(
                review_id=uuid4(),
                author_id=uuid4(),
                created_at=datetime(2026, 11, 3, 10, minute, tzinfo=UTC),
                comment=comment,
            ),
        )

    reviews = await store.list_reviews(attempt_id)

    assert [entry.comment for entry in reviews["databases"]] == ["first", "second"]
