class PracticeServiceError(Exception):
    def __init__(self, message: str, error_code: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code


class PlanNotFoundError(PracticeServiceError):
    pass


class PlanNotReadyError(PracticeServiceError):
    def __init__(self) -> None:
        super().__init__("Plan is not ready for attempts", error_code="PLAN_NOT_READY")


class AlreadyAttemptedError(PracticeServiceError):
    def __init__(self) -> None:
        super().__init__("Exercise already attempted", error_code="ALREADY_ATTEMPTED")


class InvalidExerciseCountError(PracticeServiceError):
    def __init__(self) -> None:
        super().__init__("Exercise count outside allowed range", error_code="INVALID_EXERCISE_COUNT")


class UnsupportedExerciseTypeError(PracticeServiceError):
    def __init__(self, exercise_type: str) -> None:
        super().__init__(f"Unsupported exercise type: {exercise_type}", error_code="UNSUPPORTED_EXERCISE_TYPE")


class DailyPlanQuotaExceededError(PracticeServiceError):
    def __init__(self) -> None:
        super().__init__("Daily plan quota exceeded", error_code="DAILY_PLAN_QUOTA_EXCEEDED")


class InvalidAnswerFormatError(PracticeServiceError):
    def __init__(self, message: str = "Invalid answer format") -> None:
        super().__init__(message, error_code="INVALID_ANSWER_FORMAT")


class AnswerTooLongError(PracticeServiceError):
    def __init__(self) -> None:
        super().__init__("Answer exceeds maximum length", error_code="ANSWER_TOO_LONG")


class GradingFailedError(PracticeServiceError):
    def __init__(self) -> None:
        super().__init__("Grading failed", error_code="GRADING_FAILED")


class PlanGenerationFailedError(PracticeServiceError):
    def __init__(self, message: str = "Plan generation failed") -> None:
        super().__init__(message, error_code="PLAN_GENERATION_FAILED")
