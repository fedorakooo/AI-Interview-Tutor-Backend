from shared_models.practice.exercise import Exercise, ExerciseType
from shared_models.practice.plan import PracticePlanDraft
from src.domain.exceptions.practice_errors import PlanGenerationFailedError

MVP_EXERCISE_TYPES = {
    ExerciseType.MCQ_SINGLE,
    ExerciseType.MCQ_MULTI,
    ExerciseType.OPEN_QUESTION,
    ExerciseType.FLASHCARD,
}


class ExerciseValidator:
    def __init__(self, max_exercises_per_plan: int) -> None:
        self._max_exercises = max_exercises_per_plan

    def validate(self, draft: PracticePlanDraft, *, expected_count: int) -> None:
        if not (1 <= len(draft.exercises) <= self._max_exercises):
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
