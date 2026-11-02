from shared_models.practice.exercise import Exercise


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
