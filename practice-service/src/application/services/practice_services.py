from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from shared_models.practice.exercise import Exercise, ExerciseType
from shared_models.practice.plan import PlanContextSnapshot, PracticePlanDraft
from shared_models.practice.profile import UserPracticeProfile
from src.config import settings
from src.domain.exceptions.practice_errors import PlanGenerationFailedError

MVP_EXERCISE_TYPES = {
    ExerciseType.MCQ_SINGLE,
    ExerciseType.MCQ_MULTI,
    ExerciseType.OPEN_QUESTION,
    ExerciseType.FLASHCARD,
}


class ExerciseValidator:
    def validate(self, draft: PracticePlanDraft, *, expected_count: int) -> None:
        if not (1 <= len(draft.exercises) <= settings.practice_settings.max_exercises_per_plan):
            raise PlanGenerationFailedError("Exercise count outside allowed range")
        if len(draft.exercises) != expected_count:
            raise PlanGenerationFailedError(f"Expected {expected_count} exercises, got {len(draft.exercises)}")

        seen_ids: set[str] = set()
        for exercise in draft.exercises:
            self._validate_exercise(exercise, seen_ids)

    def _validate_exercise(self, exercise: Exercise, seen_ids: set[str]) -> None:
        if exercise.type not in MVP_EXERCISE_TYPES:
            raise PlanGenerationFailedError(f"Unsupported exercise type: {exercise.type.value}")
        if not exercise.exercise_id or not exercise.title or not exercise.prompt:
            raise PlanGenerationFailedError("Exercise missing required fields")
        if exercise.exercise_id in seen_ids:
            raise PlanGenerationFailedError(f"Duplicate exercise_id: {exercise.exercise_id}")
        seen_ids.add(exercise.exercise_id)

        if exercise.type == ExerciseType.MCQ_SINGLE:
            correct = [choice for choice in exercise.choices or [] if choice.is_correct]
            if len(correct) != 1:
                raise PlanGenerationFailedError("MCQ single must have exactly one correct choice")
        elif exercise.type == ExerciseType.MCQ_MULTI:
            correct = [choice for choice in exercise.choices or [] if choice.is_correct]
            if not correct:
                raise PlanGenerationFailedError("MCQ multi must have at least one correct choice")
        elif exercise.type == ExerciseType.OPEN_QUESTION:
            if not exercise.reference_answer or len(exercise.rubric_bullets) < 2:
                raise PlanGenerationFailedError("Open question requires reference_answer and rubric bullets")
        elif exercise.type == ExerciseType.FLASHCARD:
            if not exercise.prompt or not exercise.reference_answer:
                raise PlanGenerationFailedError("Flashcard requires prompt and reference_answer")


class ExerciseSanitizer:
    @staticmethod
    def sanitize_exercise(exercise: Exercise) -> Exercise:
        payload = exercise.model_dump()
        if payload.get("choices"):
            payload["choices"] = [
                {"choice_id": choice["choice_id"], "text": choice["text"]} for choice in payload["choices"]
            ]
        payload.pop("reference_answer", None)
        payload.pop("explanation", None)
        return Exercise.model_validate(payload)

    @staticmethod
    def sanitize_plan_exercises(exercises: list[Exercise]) -> list[Exercise]:
        return [ExerciseSanitizer.sanitize_exercise(exercise) for exercise in exercises]


class QuotaService:
    def __init__(self, profile_repository) -> None:
        self._profiles = profile_repository

    async def check_and_increment(self, profile: UserPracticeProfile) -> UserPracticeProfile:
        profile = await self._profiles.reset_quota_if_needed(profile)
        if profile.plans_generated_today >= profile.daily_plan_quota:
            from src.domain.exceptions.practice_errors import DailyPlanQuotaExceededError

            raise DailyPlanQuotaExceededError()
        profile.plans_generated_today += 1
        profile.updated_at = datetime.now(UTC)
        return profile


class StreakService:
    @staticmethod
    def update_on_completion(profile: UserPracticeProfile, *, practice_date: date | None = None) -> UserPracticeProfile:
        today = practice_date or date.today()
        if profile.last_practice_date == today:
            return profile
        if profile.last_practice_date and (today - profile.last_practice_date).days == 1:
            profile.current_streak_days += 1
        elif profile.last_practice_date != today:
            profile.current_streak_days = 1
        profile.last_practice_date = today
        return profile


@dataclass
class BuiltPlanContext:
    focus_skills: list[str]
    difficulty: str
    exercise_types: list[ExerciseType]
    exercise_count: int
    source: str
    context_snapshot: PlanContextSnapshot
    interview_session_id: str | None = None
    cv_correlation_id: str | None = None
    title_hint: str | None = None
    user_goals: list[str] = field(default_factory=list)
