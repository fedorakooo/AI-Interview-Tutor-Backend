from src.domain.exceptions.interview_service_error import InterviewServiceError


class InvalidAttemptTokenError(InterviewServiceError):
    """Raised when the candidate interview token is invalid, expired or has no valid attempt id."""

    def __init__(self, message: str = "Invalid interview token") -> None:
        super().__init__(message)
