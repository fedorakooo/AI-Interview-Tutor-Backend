import logging
from dataclasses import dataclass

from fastapi import status

from src.api.v1.schemas.interview_protocol import ErrorCode
from src.domain.exceptions.assessment_context_errors import (
    AssessmentContextNotFoundError,
    AssessmentContextUnavailableError,
    AssessmentNotReadyError,
)
from src.domain.exceptions.attempt_token_error import InvalidAttemptTokenError
from src.domain.exceptions.dependency_errors import DependencyUnavailableError
from src.domain.exceptions.feedback_errors import FeedbackDisabledError, FeedbackLeakError
from src.domain.exceptions.interview_service_error import InterviewServiceError
from src.domain.exceptions.invalid_value_errors import InvalidDomainValueError
from src.domain.exceptions.report_errors import (
    FocusNotFoundError,
    InconsistentReportError,
    ReportNotReadyError,
    SessionNotCompletedError,
)
from src.domain.exceptions.session_errors import (
    EmptyInterviewerMessageError,
    EventSeqConflictError,
    InconsistentJournalError,
    NoPendingQuestionError,
    SessionBusyError,
    SessionCompletedError,
)
from src.domain.exceptions.spec_errors import EmptySpecDraftError, SpecDraftGenerationError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ErrorSpec:
    http_status: int
    detail: str
    ws_code: ErrorCode | None = None
    ws_close_code: int | None = None
    retryable: bool = False


INTERNAL_ERROR_SPEC = ErrorSpec(
    http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    detail="Internal server error",
    ws_code=ErrorCode.INTERNAL_ERROR,
    retryable=True,
)

ERROR_MAPPING: dict[type[InterviewServiceError], ErrorSpec] = {
    InvalidAttemptTokenError: ErrorSpec(
        status.HTTP_401_UNAUTHORIZED, "Invalid interview token", ErrorCode.UNAUTHORIZED, status.WS_1008_POLICY_VIOLATION
    ),
    AssessmentContextNotFoundError: ErrorSpec(
        status.HTTP_404_NOT_FOUND, "Attempt not found", ErrorCode.ASSESSMENT_UNAVAILABLE, status.WS_1011_INTERNAL_ERROR
    ),
    AssessmentNotReadyError: ErrorSpec(
        status.HTTP_409_CONFLICT,
        "Assessment is not ready",
        ErrorCode.ASSESSMENT_NOT_READY,
        status.WS_1008_POLICY_VIOLATION,
    ),
    AssessmentContextUnavailableError: ErrorSpec(
        status.HTTP_502_BAD_GATEWAY,
        "Context unavailable",
        ErrorCode.ASSESSMENT_UNAVAILABLE,
        status.WS_1011_INTERNAL_ERROR,
    ),
    ReportNotReadyError: ErrorSpec(status.HTTP_409_CONFLICT, "Report is not ready"),
    SessionNotCompletedError: ErrorSpec(status.HTTP_409_CONFLICT, "Report is not ready"),
    FocusNotFoundError: ErrorSpec(status.HTTP_404_NOT_FOUND, "Focus area not found"),
    FeedbackDisabledError: ErrorSpec(status.HTTP_404_NOT_FOUND, "Candidate feedback is disabled"),
    FeedbackLeakError: ErrorSpec(status.HTTP_422_UNPROCESSABLE_ENTITY, "Text contains internal details"),
    EmptySpecDraftError: ErrorSpec(status.HTTP_422_UNPROCESSABLE_ENTITY, "No usable draft produced"),
    SpecDraftGenerationError: ErrorSpec(status.HTTP_502_BAD_GATEWAY, "Draft generation failed"),
    SessionBusyError: ErrorSpec(
        status.HTTP_409_CONFLICT, "Interview is in progress", ErrorCode.SESSION_BUSY, retryable=True
    ),
    EventSeqConflictError: ErrorSpec(
        status.HTTP_409_CONFLICT, "Session is busy", ErrorCode.SESSION_BUSY, retryable=True
    ),
    SessionCompletedError: ErrorSpec(status.HTTP_409_CONFLICT, "Interview is completed", ErrorCode.SESSION_COMPLETED),
    DependencyUnavailableError: ErrorSpec(
        status.HTTP_503_SERVICE_UNAVAILABLE, "Service temporarily unavailable", ErrorCode.INTERNAL_ERROR, retryable=True
    ),
    InconsistentJournalError: ErrorSpec(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "Interview journal is inconsistent", ErrorCode.INTERNAL_ERROR
    ),
    InconsistentReportError: ErrorSpec(status.HTTP_500_INTERNAL_SERVER_ERROR, "Report is inconsistent"),
    InvalidDomainValueError: ErrorSpec(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "Stored data is invalid", ErrorCode.INTERNAL_ERROR
    ),
    EmptyInterviewerMessageError: ErrorSpec(
        status.HTTP_502_BAD_GATEWAY, "Interviewer returned no message", ErrorCode.INTERNAL_ERROR, retryable=True
    ),
    NoPendingQuestionError: ErrorSpec(status.HTTP_409_CONFLICT, "No question is pending", ErrorCode.INVALID_MESSAGE),
}


def resolve_error_spec(exc: BaseException) -> ErrorSpec:
    spec = ERROR_MAPPING.get(type(exc))
    if spec is None:
        logger.error("Unmapped error %s", type(exc).__name__, exc_info=exc)
        return INTERNAL_ERROR_SPEC
    return spec
