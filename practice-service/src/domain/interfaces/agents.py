from typing import Protocol

from shared_models.practice.attempt import GradingResult
from shared_models.practice.exercise import Exercise
from shared_models.practice.plan import PracticePlanDraft
from shared_models.practice.profile import DifficultyLevel


class BuiltContext(Protocol):
    focus_skills: list[str]
    difficulty: DifficultyLevel
    exercise_types: list[str]
    exercise_count: int
    source: str
    context_snapshot: dict
    interview_session_id: str | None
    cv_correlation_id: str | None


class IPlanGenerator(Protocol):
    async def generate(self, context: BuiltContext) -> PracticePlanDraft:
        pass


class IAnswerGrader(Protocol):
    async def grade_open_question(self, exercise: Exercise, user_answer: str) -> GradingResult:
        pass
