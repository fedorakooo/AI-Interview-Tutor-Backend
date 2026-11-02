class PracticeServiceError(Exception):
    """Base exception for all practice service domain errors."""

    def __init__(self, message: str, error_code: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code


class PlanNotFoundError(PracticeServiceError):
    """Raised when a practice plan does not exist."""


class PlanNotReadyError(PracticeServiceError):
    """Raised when an attempt is made on a plan that is not ready yet."""

    def __init__(self) -> None:
        super().__init__("Plan is not ready for attempts", error_code="PLAN_NOT_READY")


class AlreadyAttemptedError(PracticeServiceError):
    """Raised when an exercise has already been attempted."""

    def __init__(self) -> None:
        super().__init__("Exercise already attempted", error_code="ALREADY_ATTEMPTED")


class InvalidExerciseCountError(PracticeServiceError):
    """Raised when the requested exercise count is outside the allowed range."""

    def __init__(self) -> None:
        super().__init__("Exercise count outside allowed range", error_code="INVALID_EXERCISE_COUNT")


class UnsupportedExerciseTypeError(PracticeServiceError):
    """Raised when the exercise type is not supported."""

    def __init__(self, exercise_type: str) -> None:
        super().__init__(f"Unsupported exercise type: {exercise_type}", error_code="UNSUPPORTED_EXERCISE_TYPE")


class DailyPlanQuotaExceededError(PracticeServiceError):
    """Raised when the daily plan generation quota is exceeded."""

    def __init__(self) -> None:
        super().__init__("Daily plan quota exceeded", error_code="DAILY_PLAN_QUOTA_EXCEEDED")


class InvalidAnswerFormatError(PracticeServiceError):
    """Raised when an answer does not match the expected format."""

    def __init__(self, message: str = "Invalid answer format") -> None:
        super().__init__(message, error_code="INVALID_ANSWER_FORMAT")


class AnswerTooLongError(PracticeServiceError):
    """Raised when an answer exceeds the maximum allowed length."""

    def __init__(self) -> None:
        super().__init__("Answer exceeds maximum length", error_code="ANSWER_TOO_LONG")


class GradingFailedError(PracticeServiceError):
    """Raised when grading of an answer fails."""

    def __init__(self) -> None:
        super().__init__("Grading failed", error_code="GRADING_FAILED")


class PlanGenerationFailedError(PracticeServiceError):
    """Raised when practice plan generation fails."""

    def __init__(self, message: str = "Plan generation failed") -> None:
        super().__init__(message, error_code="PLAN_GENERATION_FAILED")
