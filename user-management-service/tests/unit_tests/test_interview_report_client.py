from uuid import uuid4

import httpx
import pytest
from shared_models.assessment import ReviewRequest, build_focus_detail, build_overview, fold_events
from shared_models.assessment.mocks import mock_assessment, mock_session_events, mock_template
from src.domain.exceptions.interview_report_errors import (
    InterviewReportNotFoundError,
    InterviewReportNotReadyError,
    InterviewReportUnavailableError,
)
from src.infrastructure.interview_service.report_client import InterviewServiceReportClient

TOKEN = "internal-secret"
TEMPLATE = mock_template()
ASSESSMENT = mock_assessment()
ATTEMPT_ID = ASSESSMENT.attempt_id


def client(handler) -> InterviewServiceReportClient:
    return InterviewServiceReportClient("http://interview-service:8001/", TOKEN, transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_overview_and_detail_are_fetched_with_the_internal_token():
    overview = build_overview(ASSESSMENT, TEMPLATE)
    detail = build_focus_detail(ASSESSMENT, TEMPLATE, fold_events(mock_session_events()), "databases")
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, request.headers["X-Internal-Service-Token"]))
        body = overview if request.url.path.endswith(str(ATTEMPT_ID)) else detail
        return httpx.Response(200, content=body.model_dump_json())

    reports = client(handler)

    assert await reports.get_overview(ATTEMPT_ID) == overview
    assert await reports.get_focus_detail(ATTEMPT_ID, "databases") == detail
    assert seen == [
        ("GET", f"/api/internal/reports/{ATTEMPT_ID}", TOKEN),
        ("GET", f"/api/internal/reports/{ATTEMPT_ID}/focus/databases", TOKEN),
    ]


@pytest.mark.asyncio
async def test_review_is_posted_with_the_author_and_verdict():
    detail = build_focus_detail(ASSESSMENT, TEMPLATE, fold_events(mock_session_events()), "async_io")
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
