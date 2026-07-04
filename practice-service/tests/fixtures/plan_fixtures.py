from shared_models.practice.exercise import Choice, Exercise, ExerciseType
from shared_models.practice.plan import PracticePlanDraft
from shared_models.practice.profile import DifficultyLevel


def sample_plan_draft(*, exercise_count: int = 3) -> PracticePlanDraft:
    exercises = [
        Exercise(
            exercise_id="mcq-1",
            type=ExerciseType.MCQ_SINGLE,
            difficulty=DifficultyLevel.MID,
            title="MCQ",
            prompt="Pick one",
            skill_tags=["Python"],
            choices=[
                Choice(choice_id="a", text="Correct", is_correct=True),
                Choice(choice_id="b", text="Wrong", is_correct=False),
            ],
            explanation="Because A is correct",
        ),
        Exercise(
            exercise_id="open-1",
            type=ExerciseType.OPEN_QUESTION,
            difficulty=DifficultyLevel.MID,
            title="Open",
            prompt="Explain REST",
            skill_tags=["API"],
            reference_answer="Representational state transfer",
            rubric_bullets=["Mentions resources", "Mentions HTTP methods"],
        ),
        Exercise(
            exercise_id="flash-1",
            type=ExerciseType.FLASHCARD,
            difficulty=DifficultyLevel.MID,
            title="Flashcard",
            prompt="What is CAP?",
            skill_tags=["Distributed Systems"],
            reference_answer="Consistency, Availability, Partition tolerance",
        ),
    ]
    return PracticePlanDraft(
        title="Test Plan",
        focus_skills=["Python", "API"],
        exercises=exercises[:exercise_count],
    )
