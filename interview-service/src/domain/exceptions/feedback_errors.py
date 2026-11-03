from src.domain.exceptions.interview_service_error import InterviewServiceError


class FeedbackError(InterviewServiceError):
    """Base exception for candidate feedback errors."""


class FeedbackDisabledError(FeedbackError):
    """Raised when candidate feedback is disabled in the interview template."""


class FeedbackLeakError(FeedbackError):
    """Raised when a feedback text contains internal details such as red flags, verdicts or reviewer comments."""
