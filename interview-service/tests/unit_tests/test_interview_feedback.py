from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic_ai.models.test import TestModel
from shared_models.assessment import (
    FeedbackView,
    ReviewRequest,
    Verdict,
)
from shared_models.assessment.mocks import mock_assessment, mock_assessment_context
from src.api.exception_handler import exception_container
from src.api.internal.router import router as internal_router
from src.config import settings
from src.domain.exceptions.feedback_errors import FeedbackDisabledError, FeedbackLeakError
from src.domain.exceptions.report_errors import ReportNotReadyError
from src.domain.interview.feedback import FeedbackDigest, build_digest, fallback_text, find_leaks
from src.infrastructure.ai.feedback_writer import PydanticFeedbackWriter, render_digest
from src.infrastructure.mongo.repositories.feedback_repository import FeedbackRepository

from tests.unit_tests.fakes import FakeStack, ScriptedFeedbackWriter
from tests.unit_tests.test_interview_report import ATTEMPT_ID, NOW, POLICY, TEMPLATE, Harness, texts

FLAG = TEMPLATE.red_flags[1]


class FeedbackHarness:
    def __init__(self, writer: ScriptedFeedbackWriter | None = None, context=None, complete: bool = True) -> None:
        self.writer = writer or ScriptedFeedbackWriter()
        self.report = Harness(texts(), complete=complete)
        self.stack = FakeStack(
            context=context or mock_assessment_context(POLICY),
            now=NOW,
            text_writer=self.report.stack.text_writer,
            feedback_writer=self.writer,
        )
        self.stack.event_repository.events.update(self.report.journal.events)
        self.container = self.stack.container
        self.store = self.stack.feedback_repository
        self.journal = self.stack.event_repository


def harness_for(writer=None, template=TEMPLATE, complete=True) -> tuple[FeedbackHarness, object]:
    context = mock_assessment_context(POLICY).model_copy(update={"template": template})
    return FeedbackHarness(writer, context, complete), template


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
    harness, template = harness_for()
    get_feedback = harness.container.get_candidate_feedback_use_case

    first = await get_feedback(ATTEMPT_ID, template)
    second = await get_feedback(ATTEMPT_ID, template)

    assert first == second and first.version == 1 and first.source == "generated"
    assert len(harness.writer.digests) == 1 and len(harness.store.versions) == 1


@pytest.mark.parametrize(
    "writer",
    [
        ScriptedFeedbackWriter(None),
        ScriptedFeedbackWriter(f"We noticed a red flag: {FLAG}"),
        ScriptedFeedbackWriter("Your verdict was weak."),
    ],
)
async def test_unsafe_or_failed_generation_falls_back_to_the_deterministic_text(writer) -> None:
    harness, template = harness_for(writer)

    feedback = await harness.container.get_candidate_feedback_use_case(ATTEMPT_ID, template)

    assert "Python fundamentals" in feedback.text and not find_leaks(feedback.text, template, [])


async def test_feedback_requires_the_template_to_allow_it_and_a_finished_interview() -> None:
    harness, template = harness_for()
    get_feedback = harness.container.get_candidate_feedback_use_case
    disabled = template.model_copy(update={"candidate_feedback": False})

    with pytest.raises(FeedbackDisabledError):
        await get_feedback(ATTEMPT_ID, disabled)
    harness.journal.events.clear()
    with pytest.raises(ReportNotReadyError):
        await get_feedback(ATTEMPT_ID, template)


async def test_edit_creates_a_new_version_and_rejects_internal_details() -> None:
    harness, template = harness_for()
    editor = uuid4()
    await harness.container.add_focus_review_use_case(
        ATTEMPT_ID,
        template,
        "async_io",
        ReviewRequest(author_id=editor, comment="Weak on loops", manual_verdict=Verdict.WEAK),
    )
    edit_feedback = harness.container.edit_candidate_feedback_use_case

    edited = await edit_feedback(ATTEMPT_ID, template, editor, "  Thanks, great talk!  ")

    assert (edited.version, edited.source, edited.editor_id, edited.text) == (
        2,
        "edited",
        editor,
        "Thanks, great talk!",
    )
    assert (await harness.store.latest(ATTEMPT_ID)).version == 2
    for text in (f"Concern: {FLAG}", "As the reviewer wrote: weak on loops"):
        with pytest.raises(FeedbackLeakError):
            await edit_feedback(ATTEMPT_ID, template, editor, text)
    assert (await harness.store.latest(ATTEMPT_ID)).version == 2


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
    store = FeedbackRepository(FakeFeedbackCollection())
    first = FeedbackView(attempt_id=ATTEMPT_ID, version=1, text="v1", source="generated", created_at=NOW)

    assert await store.append(first)
    assert not await store.append(first)
    assert await store.append(first.model_copy(update={"version": 2, "text": "v2", "source": "edited"}))

    assert (await store.latest(ATTEMPT_ID)).text == "v2"
    assert await store.latest(uuid4()) is None


TOKEN = "internal-secret"


def api(harness: FeedbackHarness) -> TestClient:
    app = FastAPI()
    app.include_router(internal_router)
    exception_container(app)
    app.state.container = harness.container
    return TestClient(app, headers={"X-Internal-Service-Token": TOKEN})


@pytest.fixture(autouse=True)
def internal_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "internal_service_token", TOKEN)


def test_internal_api_returns_and_edits_feedback() -> None:
    client = api(harness_for()[0])

    first = client.get(f"/api/internal/feedback/{ATTEMPT_ID}")
    edited = client.put(f"/api/internal/feedback/{ATTEMPT_ID}", json={"editor_id": str(uuid4()), "text": "Well done!"})

    assert first.status_code == 200 and first.json()["version"] == 1
    assert edited.status_code == 200 and edited.json()["version"] == 2 and edited.json()["text"] == "Well done!"


def test_internal_api_rejects_leaks_unfinished_interviews_and_missing_tokens() -> None:
    harness, _ = harness_for()
    client = api(harness)

    leak = client.put(f"/api/internal/feedback/{ATTEMPT_ID}", json={"editor_id": str(uuid4()), "text": f"Flag: {FLAG}"})
    assert leak.status_code == 422

    harness.journal.events.clear()
    assert client.get(f"/api/internal/feedback/{ATTEMPT_ID}").status_code == 409

    client.headers.pop("X-Internal-Service-Token")
    assert client.get(f"/api/internal/feedback/{ATTEMPT_ID}").status_code == 401


def test_internal_api_hides_feedback_when_the_template_disables_it() -> None:
    disabled = TEMPLATE.model_copy(update={"candidate_feedback": False})

    client = api(harness_for(template=disabled)[0])

    assert client.get(f"/api/internal/feedback/{ATTEMPT_ID}").status_code == 404
