from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from pymongo.errors import DuplicateKeyError
from src.domain.entities.review_entry import ReviewEntry
from src.infrastructure.mongo.repositories.assessment_repository import AssessmentRepository

from tests.fakes.builders import build_assessment


class FakeCursor:
    def __init__(self, documents: list[dict]) -> None:
        self.documents = documents

    def sort(self, key: str, direction: int) -> "FakeCursor":
        self.documents = sorted(self.documents, key=lambda document: document[key], reverse=direction < 0)
        return self

    async def to_list(self, length: int | None) -> list[dict]:
        return self.documents


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
    store = AssessmentRepository(FakeDocumentCollection(), FakeDocumentCollection())
    assessment = build_assessment()

    await store.save(assessment)
    await store.save(replace(assessment, overall_summary="A later duplicate"))

    assert await store.get(assessment.attempt_id) == assessment
    assert await store.get(uuid4()) is None


async def test_assessment_store_appends_reviews_in_creation_order() -> None:
    store = AssessmentRepository(FakeDocumentCollection(), FakeDocumentCollection())
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
