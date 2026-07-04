from unittest.mock import AsyncMock, MagicMock

import pytest
from shared_models.practice.attempt import GradingResult
from shared_models.practice.exercise import Exercise, ExerciseType
from shared_models.practice.profile import DifficultyLevel
from src.agent.answer_grader import AnswerGrader
from src.config import settings


def _open_exercise() -> Exercise:
    return Exercise(
        exercise_id="open-1",
        type=ExerciseType.OPEN_QUESTION,
        difficulty=DifficultyLevel.MID,
        title="Open",
        prompt="Explain caching",
        reference_answer="Store frequently used data",
        rubric_bullets=["Mentions cache", "Mentions eviction"],
    )


def _mock_grader_chain(result: GradingResult) -> AnswerGrader:
    grader = AnswerGrader.__new__(AnswerGrader)
    chain = MagicMock()
    chain.ainvoke = AsyncMock(return_value=result)
    grader._prompt = MagicMock()
    grader._prompt.__or__ = MagicMock(return_value=chain)
    grader._llm = MagicMock()
    return grader


class TestAnswerGraderOpenQuestion:
    @pytest.mark.asyncio
    async def test_pass_threshold_at_least_six(self) -> None:
        mock_result = GradingResult(score=7.5, is_correct=None, feedback="Solid", graded_by="llm")
        grader = _mock_grader_chain(mock_result)

        result = await grader.grade_open_question(_open_exercise(), "Caching reduces latency")

        assert result.score == 7.5
        assert result.is_correct is True
        assert result.score >= settings.practice_settings.grading_pass_threshold

    @pytest.mark.asyncio
    async def test_fails_below_threshold(self) -> None:
        mock_result = GradingResult(score=4.0, is_correct=None, feedback="Weak", graded_by="llm")
        grader = _mock_grader_chain(mock_result)

        result = await grader.grade_open_question(_open_exercise(), "I don't know")

        assert result.is_correct is False
