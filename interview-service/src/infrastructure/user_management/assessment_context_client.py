from uuid import UUID

import httpx
from pydantic import ValidationError
from shared_models.assessment import AssessmentContext

from src.domain.exceptions.assessment_context_errors import (
    AssessmentContextNotFoundError,
    AssessmentContextUnavailableError,
    AssessmentNotReadyError,
)
from src.domain.interfaces.assessment_context_client import IAssessmentContextClient


class UserManagementAssessmentContextClient(IAssessmentContextClient):
    def __init__(self, client: httpx.AsyncClient, base_url: str, service_token: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._service_token = service_token

    async def get_context(self, attempt_id: UUID) -> AssessmentContext:
        url = f"{self._base_url}/api/internal/assessment-attempts/{attempt_id}/context"
        try:
            response = await self._client.get(url, headers={"X-Internal-Service-Token": self._service_token})
        except httpx.HTTPError as exc:
            raise AssessmentContextUnavailableError() from exc

        if response.status_code == httpx.codes.NOT_FOUND:
            raise AssessmentContextNotFoundError()
        if response.status_code == httpx.codes.CONFLICT:
            raise AssessmentNotReadyError()
        if response.status_code != httpx.codes.OK:
            raise AssessmentContextUnavailableError()
        try:
            return AssessmentContext.model_validate_json(response.content)
        except ValidationError as exc:
            raise AssessmentContextUnavailableError() from exc
