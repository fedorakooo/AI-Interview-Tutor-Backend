from src.domain.exceptions.interview_service_error import InterviewServiceError


class ReportError(InterviewServiceError):
    """Base exception for assessment report errors."""


class ReportNotReadyError(ReportError):
    """Raised when a report is requested before the interview session is completed."""


class FocusNotFoundError(ReportError):
    """Raised when the focus area does not exist in the interview template."""


class SessionNotCompletedError(ReportError):
    """Raised when a report is built for an interview session that is not completed."""


class InconsistentReportError(ReportError):
    """Raised when a generated report contradicts the session journal or the template."""
