from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from shared_models.assessment import (
    CvPolicy,
    Verdict,
    fold_events,
    verify_assessment,
)
from shared_models.assessment.mocks import mock_assessment_context, mock_session_events, mock_template
from src.api.exception_handler import exception_container
from src.api.internal.router import router as internal_router
from src.application.services.assessment_report_service import GENERATOR_VERSION
from src.config import settings
from src.domain.exceptions.assessment_context_errors import AssessmentContextNotFoundError, AssessmentNotReadyError
from src.domain.exceptions.report_errors import FocusNotFoundError, ReportNotReadyError
from src.domain.interview.report_builder import SessionNotCompletedError, build_assessment
from src.domain.interview.report_dto import AssessmentDigest, AssessmentTexts, FocusText, RedFlagDraft
from src.infrastructure.ai.assessment_writer import PydanticAssessmentTextWriter, render_digest

from tests.unit_tests.fakes import FakeStack, ScriptedTextWriter

POLICY = CvPolicy.REQUIRED
TEMPLATE = mock_template(POLICY)
ATTEMPT_ID = mock_assessment_context(POLICY).attempt_id
NOW = datetime(2026, 11, 3, tzinfo=UTC)
FLAG = TEMPLATE.red_flags[1]


def events():
    return mock_session_events(POLICY)


def texts(**overrides) -> AssessmentTexts:
    values = {
        "overall_summary": "A solid backend candidate with gaps in async.",
        "focus": [
            FocusText(
                focus_id=focus.id,
                summary_short=f"Summary of {focus.id}",
                rationale=f"Rationale of {focus.id}",
                reference_comparison="Matches the reference." if focus.id in {"databases", "async_io"} else "Ignored.",
            )
            for focus in TEMPLATE.criteria
        ],
        "red_flags": [
            RedFlagDraft(flag=FLAG, quotes=["QA handles most of that on our team"], reasoning="Delegates testing.")
        ],
    }
    return AssessmentTexts(**(values | overrides))


def test_builder_uses_model_texts_but_computes_verdicts_in_code() -> None:
    assessment = build_assessment(ATTEMPT_ID, TEMPLATE, events(), texts(), GENERATOR_VERSION, NOW)

    verify_assessment(assessment, TEMPLATE, events())
    by_id = {item.focus_id: item for item in assessment.focus}
    assert by_id["databases"].summary_short == "Summary of databases"
    assert by_id["databases"].reference_comparison == "Matches the reference."
    assert by_id["api_design"].reference_comparison is None
    assert by_id["testing"].verdict == Verdict.NOT_ASSESSED
    assert assessment.overall_summary.startswith("A solid backend")
    assert assessment.red_flags[0].quotes[0].text == "QA handles most of that on our team"


def test_builder_falls_back_to_deterministic_texts_without_a_model() -> None:
    assessment = build_assessment(ATTEMPT_ID, TEMPLATE, events(), None, GENERATOR_VERSION, NOW)

    verify_assessment(assessment, TEMPLATE, events())
    assert assessment.red_flags == []
    assert "Verdicts by focus area" in assessment.overall_summary
    assert all(item.summary_short for item in assessment.focus)


def test_builder_drops_hallucinated_red_flags() -> None:
    drafts = [
        RedFlagDraft(flag="Invented flag", quotes=["QA handles most of that on our team"], reasoning="x"),
        RedFlagDraft(flag=FLAG, quotes=["words the candidate never wrote"], reasoning="x"),
    ]

    assessment = build_assessment(ATTEMPT_ID, TEMPLATE, events(), texts(red_flags=drafts), GENERATOR_VERSION, NOW)

    assert assessment.red_flags == []


def test_builder_requires_a_completed_session() -> None:
    with pytest.raises(SessionNotCompletedError):
        build_assessment(ATTEMPT_ID, TEMPLATE, events()[:-2], None, GENERATOR_VERSION, NOW)


class Harness:
    def __init__(
        self, writer_texts: AssessmentTexts | None = None, complete: bool = True, context_error: Exception | None = None
    ) -> None:
        self.stack = FakeStack(
            context=mock_assessment_context(POLICY),
            context_error=context_error,
            now=NOW,
            text_writer=ScriptedTextWriter(writer_texts),
        )
        self.container = self.stack.container
        self.journal = self.stack.event_repository
        self.store = self.stack.assessment_repository
        self.writer = self.stack.text_writer
        session_id = str(ATTEMPT_ID)
        source = events() if complete else events()[:-2]
        self.journal.events[session_id] = [e.model_copy(update={"session_id": session_id}) for e in source]


async def test_report_is_generated_once_and_cached() -> None:
    harness = Harness(texts())

    first = await harness.container.get_assessment_overview_use_case(ATTEMPT_ID, TEMPLATE)
    second = await harness.container.get_assessment_overview_use_case(ATTEMPT_ID, TEMPLATE)

    assert first == second
    assert len(harness.writer.digests) == 1
    assert first.generator_version == GENERATOR_VERSION
    assert {item.focus_id: item.verdict for item in first.focus}["async_io"] == Verdict.WEAK


async def test_writer_failure_still_produces_a_report() -> None:
    harness = Harness()

    overview = await harness.container.get_assessment_overview_use_case(ATTEMPT_ID, TEMPLATE)

    assert overview.red_flags == []
    assert len(overview.focus) == len(TEMPLATE.criteria)


async def test_report_is_not_available_before_the_interview_ends() -> None:
    for complete in (True, False):
        harness = Harness(texts(), complete=complete)
        if complete:
            harness.journal.events.clear()
        with pytest.raises(ReportNotReadyError):
            await harness.container.get_assessment_overview_use_case(ATTEMPT_ID, TEMPLATE)


async def test_focus_detail_exposes_the_timeline_with_quotes() -> None:
    detail = await Harness(texts()).container.get_focus_detail_use_case(ATTEMPT_ID, TEMPLATE, "databases")

    assert detail.reference_answer
    assert detail.timeline[0].evidence and detail.timeline[0].evidence.quotes
    with pytest.raises(FocusNotFoundError):
        await Harness(texts()).container.get_focus_detail_use_case(ATTEMPT_ID, TEMPLATE, "unknown")


async def test_reviews_are_appended_and_override_the_final_verdict() -> None:
    from shared_models.assessment import ReviewRequest

    harness = Harness(texts())
    reviewer = uuid4()

    await harness.container.add_focus_review_use_case(
        ATTEMPT_ID, TEMPLATE, "async_io", ReviewRequest(author_id=reviewer, comment="Asked again, fine")
    )
    detail = await harness.container.add_focus_review_use_case(
        ATTEMPT_ID,
        TEMPLATE,
        "async_io",
        ReviewRequest(author_id=reviewer, comment="Overall adequate", manual_verdict=Verdict.ADEQUATE),
    )
    overview = await harness.container.get_assessment_overview_use_case(ATTEMPT_ID, TEMPLATE)

    assert [entry.comment for entry in detail.focus.review] == ["Asked again, fine", "Overall adequate"]
    assert detail.focus.verdict == Verdict.WEAK and detail.focus.final_verdict == Verdict.ADEQUATE
    row = next(item for item in overview.focus if item.focus_id == "async_io")
    assert (row.verdict, row.final_verdict, row.reviewed) == (Verdict.WEAK, Verdict.ADEQUATE, True)
    assert len(harness.store.reviews) == 2


def test_digest_contains_reference_answers_for_the_writer_only_and_no_email() -> None:
    state = fold_events(events())
    digest = AssessmentDigest(TEMPLATE, state, {focus.id: (Verdict.WEAK, 0.5) for focus in TEMPLATE.criteria})

    rendered = render_digest(digest)

    assert "Reference answer: Read the plan with EXPLAIN" in rendered
    assert "Candidate answer: First I'd get the actual plan" in rendered
    assert "Alex Candidate" not in rendered and "@" not in rendered
    assert FLAG in rendered


async def test_assessment_agent_returns_structured_texts_without_a_network() -> None:
    from pydantic_ai.models.test import TestModel

    output = {
        "overall_summary": "Summary",
        "focus": [{"focus_id": "databases", "summary_short": "Short", "rationale": "Long"}],
        "red_flags": [],
    }
    writer = PydanticAssessmentTextWriter([], model=TestModel(custom_output_args=output))
    state = fold_events(events())

    result = await writer.write(
        AssessmentDigest(TEMPLATE, state, {f.id: (Verdict.WEAK, 0.5) for f in TEMPLATE.criteria})
    )

    assert result.overall_summary == "Summary" and result.focus[0].focus_id == "databases"


TOKEN = "internal-secret"


def api(harness: Harness) -> TestClient:
    app = FastAPI()
    app.include_router(internal_router)
    exception_container(app)
    app.state.container = harness.container
    return TestClient(app, headers={"X-Internal-Service-Token": TOKEN})


@pytest.fixture(autouse=True)
def internal_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "internal_service_token", TOKEN)


def test_internal_api_serves_overview_without_quotes_and_detail_with_them() -> None:
    client = api(Harness(texts()))

    overview = client.get(f"/api/internal/reports/{ATTEMPT_ID}")
    detail = client.get(f"/api/internal/reports/{ATTEMPT_ID}/focus/databases")

    assert overview.status_code == 200 and '"quotes"' not in overview.text
    assert detail.status_code == 200 and detail.json()["timeline"][0]["evidence"]["quotes"]


def test_internal_api_review_round_trip() -> None:
    client = api(Harness(texts()))

    response = client.post(
        f"/api/internal/reports/{ATTEMPT_ID}/focus/async_io/reviews",
        json={"author_id": str(uuid4()), "comment": "Looks fine", "manual_verdict": "adequate"},
    )

    assert response.status_code == 200
    assert response.json()["focus"]["final_verdict"] == "adequate"
    assert (
        client.post(
            f"/api/internal/reports/{ATTEMPT_ID}/focus/async_io/reviews", json={"author_id": "x", "comment": ""}
        ).status_code
        == 422
    )


@pytest.mark.parametrize("headers", [{}, {"X-Internal-Service-Token": "wrong"}])
def test_internal_api_requires_the_service_token(headers: dict[str, str]) -> None:
    client = api(Harness(texts()))
    client.headers.pop("X-Internal-Service-Token")

    assert client.get(f"/api/internal/reports/{ATTEMPT_ID}", headers=headers).status_code == 401


def test_internal_api_is_disabled_without_a_configured_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "internal_service_token", "")

    assert api(Harness(texts())).get(f"/api/internal/reports/{ATTEMPT_ID}").status_code == 401


@pytest.mark.parametrize(
    ("error", "status_code"),
    [(AssessmentContextNotFoundError(), 404), (AssessmentNotReadyError(), 409)],
)
def test_internal_api_maps_context_errors(error: Exception, status_code: int) -> None:
    assert (
        api(Harness(texts(), context_error=error)).get(f"/api/internal/reports/{ATTEMPT_ID}").status_code == status_code
    )


def test_internal_api_reports_unfinished_interviews_and_unknown_focus() -> None:
    unfinished = api(Harness(texts(), complete=False))
    assert unfinished.get(f"/api/internal/reports/{ATTEMPT_ID}").status_code == 409

    finished = api(Harness(texts()))
    assert finished.get(f"/api/internal/reports/{ATTEMPT_ID}/focus/unknown").status_code == 404


def test_internal_api_rejects_a_non_ascii_token_with_401_instead_of_failing() -> None:
    client = api(Harness(texts()))

    response = client.get(
        f"/api/internal/reports/{ATTEMPT_ID}", headers={"X-Internal-Service-Token": "tökén".encode("latin-1")}
    )

    assert response.status_code == 401
