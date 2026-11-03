from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from src.domain.entities.feedback_entry import FeedbackEntry
from src.infrastructure.mongo.repositories.feedback_repository import FeedbackRepository

ATTEMPT_ID = uuid4()
NOW = datetime(2026, 11, 3, tzinfo=UTC)


class FakeFeedbackCollection:
    def __init__(self) -> None:
        self.documents: list[dict] = []

    async def create_index(self, keys, **kwargs) -> None:
        return None

    async def insert_one(self, document: dict) -> None:
        from pymongo.errors import DuplicateKeyError

        if any(
            d["attempt_id"] == document["attempt_id"] and d["version"] == document["version"] for d in self.documents
        ):
            raise DuplicateKeyError("duplicate")
        self.documents.append(dict(document))

    def find(self, query: dict, projection: dict):
        found = sorted(
            (d for d in self.documents if d["attempt_id"] == query["attempt_id"]),
            key=lambda d: d["version"],
            reverse=True,
        )

        class Cursor:
            def sort(self, key, direction):
                return self

            async def to_list(self, length):
                return found[:length]

        return Cursor()


async def test_mongo_feedback_store_keeps_versions_and_returns_the_newest() -> None:
    store = FeedbackRepository(FakeFeedbackCollection())
    first = FeedbackEntry(attempt_id=ATTEMPT_ID, version=1, text="v1", source="generated", created_at=NOW)

    assert await store.append(first)
    assert not await store.append(first)
    assert await store.append(replace(first, version=2, text="v2", source="edited"))

    assert (await store.latest(ATTEMPT_ID)).text == "v2"
    assert await store.latest(uuid4()) is None
