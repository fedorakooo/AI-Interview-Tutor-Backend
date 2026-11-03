from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from jwt_handler.exceptions.token_errors import TokenError

from src.domain.exceptions.assessment_context_errors import (
    AssessmentContextNotFoundError,
    AssessmentContextUnavailableError,
    AssessmentNotReadyError,
)
from src.domain.exceptions.feedback_errors import FeedbackDisabledError, FeedbackLeakError
from src.domain.exceptions.report_errors import FocusNotFoundError, ReportNotReadyError
from src.domain.exceptions.session_errors import SessionBusyError
from src.domain.exceptions.spec_errors import EmptySpecDraftError, SpecDraftGenerationError

ERROR_RESPONSES: dict[type[Exception], tuple[int, str]] = {
    TokenError: (status.HTTP_401_UNAUTHORIZED, ""),
    AssessmentContextNotFoundError: (status.HTTP_404_NOT_FOUND, "Attempt not found"),
    AssessmentNotReadyError: (status.HTTP_409_CONFLICT, "Assessment is not ready"),
    AssessmentContextUnavailableError: (status.HTTP_502_BAD_GATEWAY, "Context unavailable"),
    ReportNotReadyError: (status.HTTP_409_CONFLICT, "Report is not ready"),
    FocusNotFoundError: (status.HTTP_404_NOT_FOUND, "Focus area not found"),
    FeedbackDisabledError: (status.HTTP_404_NOT_FOUND, "Candidate feedback is disabled"),
    FeedbackLeakError: (422, "Text contains internal details"),
    EmptySpecDraftError: (422, "No usable draft produced"),
    SpecDraftGenerationError: (status.HTTP_502_BAD_GATEWAY, "Draft generation failed"),
    SessionBusyError: (status.HTTP_409_CONFLICT, "Interview is in progress"),
}


def exception_container(app: FastAPI) -> None:
    def register(error_type: type[Exception], status_code: int, detail: str) -> None:
        @app.exception_handler(error_type)
        async def handler(request: Request, exc: Exception) -> JSONResponse:
            return JSONResponse(status_code=status_code, content={"detail": detail or str(exc)})

    for error_type, (status_code, detail) in ERROR_RESPONSES.items():
        register(error_type, status_code, detail)
