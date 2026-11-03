from datetime import UTC, datetime
from uuid import uuid4

from pymongo.errors import DuplicateKeyError
from src.domain.events.assessment_completed import AssessmentCompleted
from src.infrastructure.mongo.repositories.completion_outbox_repository import CompletionOutboxRepository


class FakeOutboxCollection:
    def __init__(self) -> None:
        self.documents: list[dict] = []

    async def create_index(self, keys, **kwargs) -> None:
        return None

    async def insert_one(self, document: dict) -> None:
        if any(d["event_id"] == document["event_id"] for d in self.documents):
            raise DuplicateKeyError("duplicate")
        self.documents.append(dict(document))

    def find(self, query: dict, projection: dict):
        found = sorted(
            (d for d in self.documents if d["published"] == query["published"]), key=lambda d: d["created_at"]
        )

        class Cursor:
            def sort(self, key, direction):
                return self

            async def to_list(self, length):
                return found[:length]

        return Cursor()

    async def update_one(self, query: dict, update: dict) -> None:
        for document in self.documents:
            if document["event_id"] == query["event_id"]:
                document.update(update["$set"])


async def test_completion_outbox_stores_once_and_lists_only_unpublished_events() -> None:
    outbox = CompletionOutboxRepository(FakeOutboxCollection())
    event = AssessmentCompleted(
        event_id=uuid4(),
        occurred_at=datetime(2026, 11, 3, tzinfo=UTC),
        correlation_id=uuid4(),
        organization_id=uuid4(),
        vacancy_id=uuid4(),
        invitation_id=uuid4(),
        attempt_id=uuid4(),
        session_id="s",
        report_reference="interview-report:s",
    )

    await outbox.enqueue(event)
    await outbox.enqueue(event)

    assert await outbox.list_pending(10) == [event]
    await outbox.mark_published(event.event_id)
    assert await outbox.list_pending(10) == []
