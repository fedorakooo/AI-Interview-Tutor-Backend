from uuid import uuid4

import httpx
import pytest
from shared_models.assessment import CvPolicy
from shared_models.assessment.mocks import mock_assessment_context
from src.domain.exceptions.assessment_context_errors import (
    AssessmentContextNotFoundError,
    AssessmentContextUnavailableError,
    AssessmentNotReadyError,
)
from src.domain.value_objects.assessment_context import AssessmentContext
from src.infrastructure.mappers.assessment_context_mapper import AssessmentContextMapper
from src.infrastructure.user_management.assessment_context_client import AssessmentContextClient

SERVICE_TOKEN = "internal-secret"


def build_client(handler: httpx.MockTransport) -> AssessmentContextClient:
    return AssessmentContextClient(
        client=httpx.AsyncClient(transport=handler),
        base_url="http://user-management:8000/",
        service_token=SERVICE_TOKEN,
    )


async def test_returns_context_and_sends_internal_token() -> None:
    context = mock_assessment_context(CvPolicy.NONE)
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=context.model_dump_json())

    result = await build_client(httpx.MockTransport(handler)).get_context(context.attempt_id)

    assert isinstance(result, AssessmentContext)
    assert result == AssessmentContextMapper.to_domain(context)
    assert (
        str(seen[0].url) == f"http://user-management:8000/api/internal/assessment-attempts/{context.attempt_id}/context"
    )
    assert seen[0].headers["X-Internal-Service-Token"] == SERVICE_TOKEN


@pytest.mark.parametrize(
    ("status_code", "error"),
    [
        (404, AssessmentContextNotFoundError),
        (409, AssessmentNotReadyError),
        (401, AssessmentContextUnavailableError),
        (500, AssessmentContextUnavailableError),
    ],
)
async def test_maps_error_statuses(status_code: int, error: type[Exception]) -> None:
    client = build_client(httpx.MockTransport(lambda request: httpx.Response(status_code)))

    with pytest.raises(error):
        await client.get_context(uuid4())


async def test_network_failure_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(AssessmentContextUnavailableError):
        await build_client(httpx.MockTransport(handler)).get_context(uuid4())


async def test_malformed_body_is_unavailable() -> None:
    client = build_client(httpx.MockTransport(lambda request: httpx.Response(200, json={"attempt_id": "nope"})))

    with pytest.raises(AssessmentContextUnavailableError):
        await client.get_context(uuid4())
