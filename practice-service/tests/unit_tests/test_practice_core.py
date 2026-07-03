from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from shared_models.practice.exercise import Choice, Exercise, ExerciseType
from shared_models.practice.messaging import PlanGenerationRequest
from shared_models.practice.plan import PracticePlanDraft
from shared_models.practice.profile import DifficultyLevel, UserPracticeProfile
from src.agent.answer_grader import AnswerGrader
from src.application.services.plan_context_builder import PlanContextBuilder
from src.application.services.practice_services import ExerciseSanitizer, ExerciseValidator, QuotaService
from src.domain.exceptions.practice_errors import DailyPlanQuotaExceededError, PlanGenerationFailedError


def _exercise(**overrides):
    base = {
        "exercise_id": "ex-1",
        "type": ExerciseType.MCQ_SINGLE,
        "difficulty": DifficultyLevel.MID,
        "title": "Title",
        "prompt": "Prompt?",
        "choices": [
            Choice(choice_id="a", text="A", is_correct=True),
            Choice(choice_id="b", text="B", is_correct=False),
        ],
    }
    base.update(overrides)
    return Exercise.model_validate(base)


class TestExerciseValidator:
    def test_accepts_valid_mcq_single(self) -> None:
        draft = PracticePlanDraft(title="Plan", focus_skills=["Python"], exercises=[_exercise()])
        ExerciseValidator().validate(draft, expected_count=1)

    def test_rejects_mcq_without_single_correct(self) -> None:
        draft = PracticePlanDraft(
            title="Plan",
            focus_skills=["Python"],
            exercises=[
                _exercise(
                    choices=[
                        Choice(choice_id="a", text="A", is_correct=False),
                        Choice(choice_id="b", text="B", is_correct=False),
                    ]
                )
            ],
        )
        with pytest.raises(PlanGenerationFailedError):
            ExerciseValidator().validate(draft, expected_count=1)


class TestExerciseSanitizer:
    def test_strips_sensitive_fields(self) -> None:
        exercise = _exercise(reference_answer="secret", explanation="because")
        sanitized = ExerciseSanitizer.sanitize_exercise(exercise)
        assert sanitized.reference_answer is None
        assert sanitized.explanation is None
        assert all(
            "is_correct" not in choice.model_dump() or choice.is_correct is False for choice in sanitized.choices or []
        )


class TestMcqGrader:
    def test_single_choice_correct(self) -> None:
        exercise = _exercise()
        result = AnswerGrader.grade_mcq_single(exercise, ["a"])
        assert result.score == 10.0
        assert result.is_correct is True

    def test_multi_choice_all_or_nothing(self) -> None:
        exercise = _exercise(
            type=ExerciseType.MCQ_MULTI,
            choices=[
                Choice(choice_id="a", text="A", is_correct=True),
                Choice(choice_id="b", text="B", is_correct=True),
                Choice(choice_id="c", text="C", is_correct=False),
            ],
        )
        correct = AnswerGrader.grade_mcq_multi(exercise, ["a", "b"])
        wrong = AnswerGrader.grade_mcq_multi(exercise, ["a"])
        assert correct.is_correct is True
        assert wrong.is_correct is False


class TestQuotaService:
    @pytest.mark.asyncio
    async def test_raises_when_quota_exceeded(self) -> None:
        profile_repo = AsyncMock()
        profile_repo.reset_quota_if_needed = AsyncMock(
            return_value=UserPracticeProfile(
                user_id=uuid4(),
                daily_plan_quota=1,
                plans_generated_today=1,
                updated_at=datetime.now(UTC),
            )
        )
        service = QuotaService(profile_repo)
        with pytest.raises(DailyPlanQuotaExceededError):
            await service.check_and_increment(profile_repo.reset_quota_if_needed.return_value)


class TestPlanContextBuilder:
    @pytest.mark.asyncio
    async def test_defaults_when_no_signals(self) -> None:
        reader = AsyncMock()
        reader.get_latest_cv = AsyncMock(return_value=None)
        reader.get_latest_interview = AsyncMock(return_value=None)
        builder = PlanContextBuilder(reader)
        profile = UserPracticeProfile(user_id=uuid4(), updated_at=datetime.now(UTC))
        request = PlanGenerationRequest()
        built = await builder.build(str(profile.user_id), request, profile)
        assert built.focus_skills == ["General CS", "Problem Solving"]
