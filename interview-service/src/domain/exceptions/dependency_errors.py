from src.domain.exceptions.interview_service_error import InterviewServiceError


class DependencyUnavailableError(InterviewServiceError):
    """Raised when a storage or lock backend fails and the operation can be retried later."""
