from langchain_core.prompts import ChatPromptTemplate
from shared_models.practice.attempt import GradingResult
from shared_models.practice.exercise import Exercise, ExerciseType, FlashcardRating
from src.agent.prompts.templates import OPEN_QUESTION_GRADING_SYSTEM_PROMPT
from src.config import settings
from src.infrastructure.llm.factory import LLMFactory

FLASHCARD_SCORE_MAP = {
    FlashcardRating.AGAIN: 0.0,
    FlashcardRating.GOOD: 7.0,
    FlashcardRating.EASY: 10.0,
}


class AnswerGrader:
    def __init__(self) -> None:
        self._llm = LLMFactory.create_grader_llm().with_structured_output(GradingResult)
        self._prompt = ChatPromptTemplate.from_messages(
            [
                ("system", OPEN_QUESTION_GRADING_SYSTEM_PROMPT),
                (
                    "human",
                    "Exercise prompt: {prompt}\nRubric: {rubric}\nReference answer: {reference}\n"
                    "Candidate answer: {answer}\nPass threshold: {threshold}",
                ),
            ]
        )

    async def grade_open_question(self, exercise: Exercise, user_answer: str) -> GradingResult:
        chain = self._prompt | self._llm
        result = await chain.ainvoke(
            {
                "prompt": exercise.prompt,
                "rubric": "; ".join(exercise.rubric_bullets),
                "reference": exercise.reference_answer or "",
                "answer": user_answer,
                "threshold": settings.practice_settings.grading_pass_threshold,
            }
        )
        grading = result if isinstance(result, GradingResult) else GradingResult.model_validate(result)
        grading.graded_by = "llm"
        if grading.is_correct is None:
            grading.is_correct = grading.score >= settings.practice_settings.grading_pass_threshold
        return grading

    @staticmethod
    def grade_mcq_single(exercise: Exercise, selected_choice_ids: list[str]) -> GradingResult:
        correct_ids = {choice.choice_id for choice in exercise.choices or [] if choice.is_correct}
        selected = set(selected_choice_ids)
        is_correct = selected == correct_ids and len(correct_ids) == 1
        feedback = exercise.explanation or ("Correct." if is_correct else "Incorrect.")
        return GradingResult(
            score=10.0 if is_correct else 0.0,
            is_correct=is_correct,
            feedback=feedback,
            graded_by="deterministic",
        )

    @staticmethod
    def grade_mcq_multi(exercise: Exercise, selected_choice_ids: list[str]) -> GradingResult:
        correct_ids = {choice.choice_id for choice in exercise.choices or [] if choice.is_correct}
        selected = set(selected_choice_ids)
        is_correct = selected == correct_ids
        feedback = exercise.explanation or ("Correct." if is_correct else "Incorrect.")
        return GradingResult(
            score=10.0 if is_correct else 0.0,
            is_correct=is_correct,
            feedback=feedback,
            graded_by="deterministic",
        )

    @staticmethod
    def grade_flashcard(rating: FlashcardRating) -> GradingResult:
        score = FLASHCARD_SCORE_MAP[rating]
        return GradingResult(
            score=score,
            is_correct=rating != FlashcardRating.AGAIN,
            feedback="Self-assessed flashcard rating recorded.",
            graded_by="self",
        )

    @staticmethod
    def find_exercise(plan, exercise_id: str) -> Exercise | None:
        for exercise in plan.exercises:
            if exercise.exercise_id == exercise_id:
                return exercise
        return None

    @staticmethod
    def supported_types() -> set[ExerciseType]:
        return {
            ExerciseType.MCQ_SINGLE,
            ExerciseType.MCQ_MULTI,
            ExerciseType.OPEN_QUESTION,
            ExerciseType.FLASHCARD,
        }
