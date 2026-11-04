from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from shared_models.assessment import (
    AssessmentCoverageView,
    AssessmentOverview,
    EvidenceLevel,
    EvidenceView,
    FocusAssessmentView,
    FocusDetail,
    FocusOverview,
    QuoteView,
    RedFlagOverview,
    ReviewRequest,
    TimelineEntry,
    Verdict,
)
from src.domain.exceptions.interview_report_errors import (
    InterviewReportNotFoundError,
    InterviewReportNotReadyError,
    InterviewReportUnavailableError,
)
from src.infrastructure.interview_service.report_client import InterviewServiceReportClient

TOKEN = "internal-secret"
ATTEMPT_ID = UUID("5b0e5a52-3a27-4d36-8d0b-2f6a0b8d7c11")
ANSWER = "I would run EXPLAIN ANALYZE first and then add a composite index."


def focus_detail(focus_id: str) -> FocusDetail:
    evidence = EvidenceView(
        evidence_id=UUID("0b4f4a9e-6f3a-4a5c-8d57-1c2f3d4e5f60"),
        focus_id=focus_id,
        question_seq=2,
        answer_seq=3,
        level=EvidenceLevel.STRONG,
        matched_signals=["Chooses indexes based on query plans"],
        quotes=[QuoteView(event_seq=3, start=8, end=23, text="EXPLAIN ANALYZE")],
        reasoning="Plan-first investigation.",
    )
    return FocusDetail(
        focus=FocusAssessmentView(
            focus_id=focus_id,
            verdict=Verdict.STRONG,
            confidence=0.75,
            summary_short="Strong query investigation.",
            rationale="The answer is plan-driven with a safe index rollout.",
            evidence=[evidence],
        ),
        skill="SQL and PostgreSQL",
        required=True,
        weight=25,
        expected_level="middle",
        reference_answer="Read the plan with EXPLAIN (ANALYZE, BUFFERS).",
        timeline=[
            TimelineEntry(
                question_seq=2,
                question_text="A report query became slow. How do you investigate?",
                answer_seq=3,
                answer_text=ANSWER,
                custom_question=True,
                evidence=evidence,
            )
        ],
    )


def overview() -> AssessmentOverview:
    return AssessmentOverview(
        assessment_id=UUID("7c1d2e3f-4a5b-4c6d-8e7f-9a0b1c2d3e4f"),
        attempt_id=ATTEMPT_ID,
        template_version=2,
        report_version=1,
        generator_version="test-1",
        generated_at=datetime(2026, 11, 2, 11, 0, tzinfo=UTC),
        coverage=AssessmentCoverageView(
            focus_total=2, focus_assessed=1, required_total=1, required_assessed=1, questions_asked=4
        ),
        overall_summary="Strong on databases; async knowledge could not be assessed.",
        focus=[
            FocusOverview(
                focus_id="databases",
                skill="SQL and PostgreSQL",
                required=True,
                weight=60,
                verdict=Verdict.STRONG,
                final_verdict=Verdict.STRONG,
                confidence=0.75,
                summary_short="Strong query investigation.",
                evidence_count=2,
                matched_strong_signals=["Chooses indexes based on query plans"],
                covered_must_cover=["indexes"],
                missed_must_cover=["N+1 queries"],
                reviewed=False,
            ),
            FocusOverview(
                focus_id="async_io",
                skill="Async and concurrency",
                required=False,
                weight=40,
                verdict=Verdict.NOT_ASSESSED,
                final_verdict=Verdict.NOT_ASSESSED,
                confidence=0.2,
                summary_short="Only one answer collected.",
                evidence_count=1,
                reviewed=False,
            ),
        ],
        red_flags=[RedFlagOverview(flag="Dismisses automated testing", reasoning="Attributes testing to QA.")],
    )


def client(handler) -> InterviewServiceReportClient:
    return InterviewServiceReportClient("http://interview-service:8001/", TOKEN, transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_overview_and_detail_are_fetched_with_the_internal_token():
    expected_overview = overview()
    detail = focus_detail("databases")
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, request.headers["X-Internal-Service-Token"]))
        body = expected_overview if request.url.path.endswith(str(ATTEMPT_ID)) else detail
        return httpx.Response(200, content=body.model_dump_json())

    reports = client(handler)

    assert await reports.get_overview(ATTEMPT_ID) == expected_overview
    assert await reports.get_focus_detail(ATTEMPT_ID, "databases") == detail
    assert seen == [
        ("GET", f"/api/internal/reports/{ATTEMPT_ID}", TOKEN),
        ("GET", f"/api/internal/reports/{ATTEMPT_ID}/focus/databases", TOKEN),
    ]


@pytest.mark.asyncio
async def test_review_is_posted_with_the_author_and_verdict():
    detail = focus_detail("async_io")
    posted = []

    def handler(request: httpx.Request) -> httpx.Response:
        posted.append((request.method, request.url.path, request.content))
        return httpx.Response(200, content=detail.model_dump_json())

    author = uuid4()
    await client(handler).add_review(
        ATTEMPT_ID, "async_io", ReviewRequest(author_id=author, comment="Fine", manual_verdict="adequate")
    )

    method, path, content = posted[0]
    assert (method, path) == ("POST", f"/api/internal/reports/{ATTEMPT_ID}/focus/async_io/reviews")
    assert str(author).encode() in content and b"adequate" in content


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "error"),
    [
        (404, InterviewReportNotFoundError),
        (409, InterviewReportNotReadyError),
        (401, InterviewReportUnavailableError),
        (500, InterviewReportUnavailableError),
    ],
)
async def test_error_statuses_become_domain_errors(status_code, error):
    reports = client(lambda request: httpx.Response(status_code))

    with pytest.raises(error):
        await reports.get_overview(ATTEMPT_ID)


@pytest.mark.asyncio
async def test_network_failure_and_malformed_body_are_unavailable():
    def failing(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(InterviewReportUnavailableError):
        await client(failing).get_overview(ATTEMPT_ID)
    with pytest.raises(InterviewReportUnavailableError):
        await client(lambda request: httpx.Response(200, json={"nope": 1})).get_overview(ATTEMPT_ID)
