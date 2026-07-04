from typing import Protocol

from shared_models.practice.attempt import GradingResult
from shared_models.practice.exercise import Exercise
from shared_models.practice.plan import PracticePlanDraft
from shared_models.practice.profile import DifficultyLevel


class BuiltContext(Protocol):
    """Normalized inputs passed from the context builder to plan generation."""

    focus_skills: list[str]
    difficulty: DifficultyLevel
    exercise_types: list[str]
    exercise_count: int
    source: str
    context_snapshot: dict
    interview_session_id: str | None
    cv_correlation_id: str | None


class IPlanGenerator(Protocol):
    """LLM port for generating structured practice plan drafts."""

    async def generate(self, context: BuiltContext) -> PracticePlanDraft:
        """Generate exercises for the given personalization context."""
        pass


class IAnswerGrader(Protocol):
    """LLM port for grading open-ended exercise answers."""

    async def grade_open_question(self, exercise: Exercise, user_answer: str) -> GradingResult:
        """Grade a free-text answer against the exercise rubric."""
        pass
