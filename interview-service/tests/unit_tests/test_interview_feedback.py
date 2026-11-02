from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic_ai.models.test import TestModel
from shared_models.assessment import (
    AssessmentContext,
    FeedbackView,
    ReviewRequest,
    Verdict,
)
from shared_models.assessment.mocks import mock_assessment, mock_assessment_context, mock_template
from src.api.internal.feedback import router
from src.application.interview.feedback_service import CandidateFeedbackService
from src.config import settings
from src.domain.exceptions.feedback_errors import FeedbackDisabledError, FeedbackLeakError
from src.domain.exceptions.report_errors import ReportNotReadyError
from src.domain.interfaces.assessment_context_client import IAssessmentContextClient
from src.domain.interfaces.feedback_store import IFeedbackStore
from src.domain.interfaces.feedback_writer import IFeedbackWriter
from src.domain.interview.feedback import FeedbackDigest, build_digest, fallback_text, find_leaks
from src.infrastructure.ai.feedback_writer import PydanticFeedbackWriter, render_digest
from src.infrastructure.mongo_feedback_store import MongoFeedbackStore

from tests.unit_tests.test_interview_report import ATTEMPT_ID, NOW, POLICY, TEMPLATE, Harness, texts

FLAG = TEMPLATE.red_flags[1]


class InMemoryFeedbackStore(IFeedbackStore):
    def __init__(self) -> None:
        self.versions: list[FeedbackView] = []

    async def latest(self, attempt_id: UUID) -> FeedbackView | None:
        return max((v for v in self.versions if v.attempt_id == attempt_id), key=lambda v: v.version, default=None)

    async def append(self, feedback: FeedbackView) -> bool:
        if any(v.attempt_id == feedback.attempt_id and v.version == feedback.version for v in self.versions):
            return False
        self.versions.append(feedback)
        return True


class ScriptedFeedbackWriter(IFeedbackWriter):
    def __init__(self, text: str | None = "Thank you! You did well on Python fundamentals.") -> None:
        self.text = text
        self.digests: list[FeedbackDigest] = []

    async def write(self, digest: FeedbackDigest) -> str:
        self.digests.append(digest)
        if self.text is None:
            raise RuntimeError("model unavailable")
        return self.text


def service(writer: ScriptedFeedbackWriter | None = None, template=TEMPLATE):
    harness = Harness(texts())
    store = InMemoryFeedbackStore()
    writer = writer or ScriptedFeedbackWriter()
    return CandidateFeedbackService(harness.service, store, writer, clock=lambda: NOW), store, writer, harness, template


def test_digest_contains_only_skill_names_and_missed_topics() -> None:
    digest = build_digest(mock_assessment(POLICY), TEMPLATE)

    assert digest.strengths == ["Python fundamentals", "SQL and PostgreSQL", "REST API design with FastAPI"]
    assert "Async and concurrency (blocking calls, task cancellation)" in digest.growth
    assert "Testing and code quality (unit vs integration tests)" in digest.growth
    assert not find_leaks(render_digest(digest), TEMPLATE, [])


@pytest.mark.parametrize("language", ["en", "ru", "de"])
def test_fallback_text_is_safe_in_every_language(language: str) -> None:
    digest = build_digest(mock_assessment(POLICY), TEMPLATE)

    text = fallback_text(FeedbackDigest(language, digest.strengths, digest.growth))

    assert "Python fundamentals" in text and not find_leaks(text, TEMPLATE, [])


def test_leak_detection_covers_red_flags_review_comments_and_internal_words() -> None:
    assert find_leaks(f"Note: {FLAG.lower()}.", TEMPLATE, [])
    assert find_leaks("Great job!", TEMPLATE, ["Needs a second look"]) == []
    assert find_leaks("The reviewer said needs a second look", TEMPLATE, ["Needs a second look"])
    assert find_leaks("Your verdict is weak", TEMPLATE, [])
    assert find_leaks("You showed real confidence with Python.", TEMPLATE, []) == []


async def test_feedback_is_generated_once_and_cached() -> None:
    feedback_service, store, writer, _, template = service()

    first = await feedback_service.get(ATTEMPT_ID, template)
    second = await feedback_service.get(ATTEMPT_ID, template)

    assert first == second and first.version == 1 and first.source == "generated"
    assert len(writer.digests) == 1 and len(store.versions) == 1


@pytest.mark.parametrize(
    "writer",
    [
        ScriptedFeedbackWriter(None),
        ScriptedFeedbackWriter(f"We noticed a red flag: {FLAG}"),
        ScriptedFeedbackWriter("Your verdict was weak."),
    ],
)
async def test_unsafe_or_failed_generation_falls_back_to_the_deterministic_text(writer) -> None:
    feedback_service, _, _, _, template = service(writer)

    feedback = await feedback_service.get(ATTEMPT_ID, template)

    assert "Python fundamentals" in feedback.text and not find_leaks(feedback.text, template, [])


async def test_feedback_requires_the_template_to_allow_it_and_a_finished_interview() -> None:
    feedback_service, _, _, harness, template = service()
    disabled = template.model_copy(update={"candidate_feedback": False})

    with pytest.raises(FeedbackDisabledError):
        await feedback_service.get(ATTEMPT_ID, disabled)
    harness.journal.events.clear()
    with pytest.raises(ReportNotReadyError):
        await feedback_service.get(ATTEMPT_ID, template)


async def test_edit_creates_a_new_version_and_rejects_internal_details() -> None:
    feedback_service, store, _, harness, template = service()
    editor = uuid4()
    await harness.service.add_review(
        ATTEMPT_ID,
        template,
        "async_io",
        ReviewRequest(author_id=editor, comment="Weak on loops", manual_verdict=Verdict.WEAK),
    )

    edited = await feedback_service.edit(ATTEMPT_ID, template, editor, "  Thanks, great talk!  ")

    assert (edited.version, edited.source, edited.editor_id, edited.text) == (
        2,
        "edited",
        editor,
        "Thanks, great talk!",
    )
    assert (await store.latest(ATTEMPT_ID)).version == 2
    for text in (f"Concern: {FLAG}", "As the reviewer wrote: weak on loops"):
        with pytest.raises(FeedbackLeakError):
            await feedback_service.edit(ATTEMPT_ID, template, editor, text)
    assert (await store.latest(ATTEMPT_ID)).version == 2


async def test_feedback_writer_agent_returns_text_without_a_network() -> None:
    writer = PydanticFeedbackWriter([], model=TestModel(custom_output_text="  Nice work!  "))

    assert await writer.write(FeedbackDigest("en", ["Python"], ["SQL"])) == "Nice work!"


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
    store = MongoFeedbackStore(FakeFeedbackCollection())
    first = FeedbackView(attempt_id=ATTEMPT_ID, version=1, text="v1", source="generated", created_at=NOW)

    assert await store.append(first)
    assert not await store.append(first)
    assert await store.append(first.model_copy(update={"version": 2, "text": "v2", "source": "edited"}))

    assert (await store.latest(ATTEMPT_ID)).text == "v2"
    assert await store.latest(uuid4()) is None


class FakeContextClient(IAssessmentContextClient):
    async def get_context(self, attempt_id: UUID) -> AssessmentContext:
        return mock_assessment_context(POLICY)


TOKEN = "internal-secret"


def api(feedback_service: CandidateFeedbackService) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.candidate_feedback_service = feedback_service
    app.state.assessment_context_client = FakeContextClient()
    return TestClient(app, headers={"X-Internal-Service-Token": TOKEN})


@pytest.fixture(autouse=True)
def internal_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "internal_service_token", TOKEN)


def test_internal_api_returns_and_edits_feedback() -> None:
    client = api(service()[0])

    first = client.get(f"/api/internal/feedback/{ATTEMPT_ID}")
    edited = client.put(f"/api/internal/feedback/{ATTEMPT_ID}", json={"editor_id": str(uuid4()), "text": "Well done!"})

    assert first.status_code == 200 and first.json()["version"] == 1
    assert edited.status_code == 200 and edited.json()["version"] == 2 and edited.json()["text"] == "Well done!"


def test_internal_api_rejects_leaks_unfinished_interviews_and_missing_tokens() -> None:
    feedback_service, _, _, harness, _ = service()
    client = api(feedback_service)

    leak = client.put(f"/api/internal/feedback/{ATTEMPT_ID}", json={"editor_id": str(uuid4()), "text": f"Flag: {FLAG}"})
    assert leak.status_code == 422

    harness.journal.events.clear()
    assert client.get(f"/api/internal/feedback/{uuid4()}").status_code in (200, 409)
    assert client.get(f"/api/internal/feedback/{ATTEMPT_ID}").status_code == 409

    client.headers.pop("X-Internal-Service-Token")
    assert client.get(f"/api/internal/feedback/{ATTEMPT_ID}").status_code == 401


def test_internal_api_hides_feedback_when_the_template_disables_it() -> None:
    class DisabledContext(IAssessmentContextClient):
        async def get_context(self, attempt_id: UUID) -> AssessmentContext:
            context = mock_assessment_context(POLICY)
            return context.model_copy(
                update={"template": mock_template(POLICY).model_copy(update={"candidate_feedback": False})}
            )

    client = api(service()[0])
    client.app.state.assessment_context_client = DisabledContext()

    assert client.get(f"/api/internal/feedback/{ATTEMPT_ID}").status_code == 404
