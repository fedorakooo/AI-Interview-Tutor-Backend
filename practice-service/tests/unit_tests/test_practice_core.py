from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from shared_models.cv.cv_data import CVData
from shared_models.interview.report import InterviewReport, SkillScore
from shared_models.practice.exercise import Choice, Exercise, ExerciseType
from shared_models.practice.messaging import PlanGenerationRequest
from shared_models.practice.plan import PlanSource, PracticePlanDraft
from shared_models.practice.profile import DevelopmentGoal, DifficultyLevel, UserPracticeProfile
from src.agent.answer_grader import AnswerGrader
from src.application.services.plan_context_builder import PlanContextBuilder
from src.application.services.practice_services import ExerciseSanitizer, ExerciseValidator, QuotaService
from src.domain.exceptions.practice_errors import DailyPlanQuotaExceededError, PlanGenerationFailedError
from src.infrastructure.mongo.context_reader import CVContextData, InterviewContextData


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

    def test_rejects_open_question_without_rubric(self) -> None:
        draft = PracticePlanDraft(
            title="Plan",
            focus_skills=["Python"],
            exercises=[
                _exercise(
                    type=ExerciseType.OPEN_QUESTION,
                    choices=None,
                    reference_answer="Expected answer",
                    rubric_bullets=["Only one bullet"],
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

    @pytest.mark.asyncio
    async def test_increments_when_under_quota(self) -> None:
        profile = UserPracticeProfile(
            user_id=uuid4(),
            daily_plan_quota=3,
            plans_generated_today=1,
            updated_at=datetime.now(UTC),
        )
        profile_repo = AsyncMock()
        profile_repo.reset_quota_if_needed = AsyncMock(return_value=profile)
        service = QuotaService(profile_repo)

        updated = await service.check_and_increment(profile)

        assert updated.plans_generated_today == 2

    @pytest.mark.asyncio
    async def test_resets_quota_on_new_day(self) -> None:
        yesterday = date.today() - timedelta(days=1)
        profile = UserPracticeProfile(
            user_id=uuid4(),
            daily_plan_quota=3,
            plans_generated_today=3,
            quota_reset_date=yesterday,
            updated_at=datetime.now(UTC),
        )
        profile_repo = AsyncMock()

        async def reset_if_needed(current: UserPracticeProfile) -> UserPracticeProfile:
            if current.quota_reset_date != date.today():
                current.plans_generated_today = 0
                current.quota_reset_date = date.today()
            return current

        profile_repo.reset_quota_if_needed = AsyncMock(side_effect=reset_if_needed)
        service = QuotaService(profile_repo)

        updated = await service.check_and_increment(profile)

        assert updated.plans_generated_today == 1
        assert updated.quota_reset_date == date.today()


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

    @pytest.mark.asyncio
    async def test_cv_only_context(self) -> None:
        reader = AsyncMock()
        reader.get_latest_cv = AsyncMock(
            return_value=CVContextData(
                correlation_id="cv-123",
                cv_data=CVData(user_name="Jane Doe", skills=[{"name": "Python"}, {"name": "PostgreSQL"}]),
            )
        )
        reader.get_latest_interview = AsyncMock(return_value=None)
        builder = PlanContextBuilder(reader)
        profile = UserPracticeProfile(user_id=uuid4(), updated_at=datetime.now(UTC))
        built = await builder.build(str(profile.user_id), PlanGenerationRequest(), profile)
        assert "Python" in built.focus_skills
        assert built.source == PlanSource.CV.value

    @pytest.mark.asyncio
    async def test_interview_only_context(self) -> None:
        reader = AsyncMock()
        reader.get_latest_cv = AsyncMock(return_value=None)
        reader.get_latest_interview = AsyncMock(
            return_value=InterviewContextData(
                session_id="session-1",
                cv_correlation_id=None,
                report=InterviewReport(
                    summary="Summary",
                    weaknesses=["Cache invalidation"],
                    skill_scores=[SkillScore(skill="Redis", score=4.0)],
                ),
            )
        )
        builder = PlanContextBuilder(reader)
        profile = UserPracticeProfile(user_id=uuid4(), updated_at=datetime.now(UTC))
        built = await builder.build(str(profile.user_id), PlanGenerationRequest(), profile)
        assert "Cache invalidation" in built.focus_skills
        assert "Redis" in built.focus_skills
        assert built.source == PlanSource.INTERVIEW.value

    @pytest.mark.asyncio
    async def test_combined_context_deduplicates_skills(self) -> None:
        reader = AsyncMock()
        reader.get_latest_cv = AsyncMock(
            return_value=CVContextData(
                correlation_id="cv-123",
                cv_data=CVData(user_name="Jane Doe", skills=[{"name": "Python"}]),
            )
        )
        reader.get_latest_interview = AsyncMock(
            return_value=InterviewContextData(
                session_id="session-1",
                cv_correlation_id="cv-123",
                report=InterviewReport(summary="Summary", weaknesses=["Python"]),
            )
        )
        builder = PlanContextBuilder(reader)
        profile = UserPracticeProfile(
            user_id=uuid4(),
            development_goals=[DevelopmentGoal(skill="Python", priority=1)],
            updated_at=datetime.now(UTC),
        )
        built = await builder.build(str(profile.user_id), PlanGenerationRequest(), profile)
        assert built.focus_skills.count("Python") == 1
        assert built.source == PlanSource.COMBINED.value
