from uuid import uuid4

from src.infrastructure.mongo.repositories.candidate_cv_repository import CandidateCvRepository


class FakeCvCollection:
    def __init__(self, document: dict | None) -> None:
        self.document = document
        self.queries: list[tuple] = []

    async def find_one(self, query: dict, sort: list | None = None):
        self.queries.append((query, sort))
        return self.document


async def test_cv_provider_strips_metadata_and_looks_up_by_correlation_id() -> None:
    correlation_id = uuid4()
    repository = FakeCvCollection(
        {
            "_id": "x",
            "correlation_id": str(correlation_id),
            "user_id": "u",
            "status": "completed",
            "specialization": "Backend",
        }
    )

    cv = await CandidateCvRepository(repository).get(correlation_id)

    assert cv is not None and cv.specialization == "Backend"
    assert repository.queries == [
        ({"correlation_id": str(correlation_id), "status": "completed"}, [("published_at", -1)])
    ]


async def test_cv_provider_returns_nothing_for_a_missing_document() -> None:
    assert await CandidateCvRepository(FakeCvCollection(None)).get(uuid4()) is None
