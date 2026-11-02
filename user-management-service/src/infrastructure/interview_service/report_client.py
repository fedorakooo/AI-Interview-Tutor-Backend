from uuid import UUID

import httpx
from pydantic import BaseModel, ValidationError
from shared_models.assessment import AssessmentOverview, FocusDetail, ReviewRequest

from src.domain.exceptions.interview_report_errors import (
    InterviewReportNotFoundError,
    InterviewReportNotReadyError,
    InterviewReportUnavailableError,
)
from src.domain.interfaces.reports.interview_report_client import IInterviewReportClient


class InterviewServiceReportClient(IInterviewReportClient):
    def __init__(
        self,
        base_url: str,
        service_token: str,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._transport = transport
        self._base_url = base_url.rstrip("/")
        self._service_token = service_token
        self._timeout = timeout_seconds

    async def get_overview(self, attempt_id: UUID) -> AssessmentOverview:
        return await self._request("GET", f"/api/internal/reports/{attempt_id}", AssessmentOverview)

    async def get_focus_detail(self, attempt_id: UUID, focus_id: str) -> FocusDetail:
        return await self._request("GET", f"/api/internal/reports/{attempt_id}/focus/{focus_id}", FocusDetail)

    async def add_review(self, attempt_id: UUID, focus_id: str, request: ReviewRequest) -> FocusDetail:
        return await self._request(
            "POST",
            f"/api/internal/reports/{attempt_id}/focus/{focus_id}/reviews",
            FocusDetail,
            body=request.model_dump(mode="json"),
        )

    async def _request[T: BaseModel](self, method: str, path: str, model: type[T], body: dict | None = None) -> T:
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await client.request(
                    method,
                    self._base_url + path,
                    json=body,
                    headers={"X-Internal-Service-Token": self._service_token},
                )
        except httpx.HTTPError as exc:
            raise InterviewReportUnavailableError() from exc

        if response.status_code == httpx.codes.NOT_FOUND:
            raise InterviewReportNotFoundError()
        if response.status_code == httpx.codes.CONFLICT:
            raise InterviewReportNotReadyError()
        if response.status_code != httpx.codes.OK:
            raise InterviewReportUnavailableError()
        try:
            return model.model_validate_json(response.content)
        except ValidationError as exc:
            raise InterviewReportUnavailableError() from exc
