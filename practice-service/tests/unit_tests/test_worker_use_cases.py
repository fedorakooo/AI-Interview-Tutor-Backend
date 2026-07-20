from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pymongo.errors import DuplicateKeyError
from shared_models.interview.report import InterviewReport
from shared_models.practice.exercise import ExerciseType, FlashcardRating
from shared_models.practice.messaging import InterviewCompletedEvent, PlanGenerationRequest, PracticePlanJobMessage
from shared_models.practice.plan import PlanContextSnapshot, PlanSource, PlanStatus, PracticePlan
from shared_models.practice.profile import DifficultyLevel, UserPracticeProfile
from src.agent.answer_grader import AnswerGrader
from src.application.services.practice_services import BuiltPlanContext, ExerciseValidator
from src.application.use_cases.worker_use_cases import (
    GeneratePlanUseCase,
    HandleInterviewCompletedUseCase,
    SubmitAttemptUseCase,
)
from src.domain.exceptions.practice_errors import AlreadyAttemptedError, PlanGenerationFailedError, PlanNotReadyError
from src.infrastructure.mongo.repositories import ProfileRepository

from tests.fixtures.plan_fixtures import sample_plan_draft


def _default_profile(user_id):
    return ProfileRepository.default_profile(user_id)


def _ready_plan(**overrides) -> PracticePlan:
    now = datetime.now(UTC)
    base = {
        "plan_id": uuid4(),
        "user_id": uuid4(),
        "source": PlanSource.MANUAL,
        "status": PlanStatus.READY,
        "title": "Plan",
        "focus_skills": ["Python"],
        "difficulty": DifficultyLevel.MID,
        "context_snapshot": PlanContextSnapshot(focus_skills=["Python"], difficulty=DifficultyLevel.MID),
        "exercises": sample_plan_draft().exercises,
        "exercise_count": 3,
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    return PracticePlan.model_validate(base)


def _built_context() -> BuiltPlanContext:
    return BuiltPlanContext(
        focus_skills=["Python"],
        difficulty="mid",
        exercise_types=[ExerciseType.MCQ_SINGLE],
        exercise_count=3,
        source=PlanSource.MANUAL.value,
        context_snapshot=PlanContextSnapshot(focus_skills=["Python"], difficulty=DifficultyLevel.MID),
    )


class TestGeneratePlanUseCase:
    @pytest.mark.asyncio
    async def test_skips_when_plan_already_ready(self) -> None:
        plan = _ready_plan()
        plan_repo = AsyncMock()
        plan_repo.get_plan_by_id = AsyncMock(return_value=plan)
        plan_generator = AsyncMock()
        use_case = GeneratePlanUseCase(
            plan_repo,
            AsyncMock(),
            AsyncMock(),
            plan_generator,
            ExerciseValidator(),
        )

        await use_case.execute(
            PracticePlanJobMessage(
                job_id=uuid4(),
                plan_id=plan.plan_id,
                user_id=plan.user_id,
                source=PlanSource.MANUAL,
                request=PlanGenerationRequest(exercise_count=3),
                published_at=datetime.now(UTC),
            )
        )

        plan_repo.try_claim_plan_generation.assert_not_called()
        plan_generator.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_pending_claim_lost_race(self) -> None:
        pending = _ready_plan(status=PlanStatus.PENDING)
        plan_repo = AsyncMock()
        plan_repo.get_plan_by_id = AsyncMock(return_value=pending)
        plan_repo.try_claim_plan_generation = AsyncMock(return_value=None)
        plan_generator = AsyncMock()
        use_case = GeneratePlanUseCase(
            plan_repo,
            AsyncMock(),
            AsyncMock(),
            plan_generator,
            ExerciseValidator(),
        )

        await use_case.execute(
            PracticePlanJobMessage(
                job_id=uuid4(),
                plan_id=pending.plan_id,
                user_id=pending.user_id,
                source=PlanSource.MANUAL,
                request=PlanGenerationRequest(exercise_count=3),
                published_at=datetime.now(UTC),
            )
        )

        plan_generator.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_marks_failed_on_validation_error(self) -> None:
        pending = _ready_plan(status=PlanStatus.PENDING)
        claimed = _ready_plan(status=PlanStatus.GENERATING, plan_id=pending.plan_id, user_id=pending.user_id)
        plan_repo = AsyncMock()
        plan_repo.get_plan_by_id = AsyncMock(return_value=pending)
        plan_repo.try_claim_plan_generation = AsyncMock(return_value=claimed)
        profile_repo = AsyncMock()
        profile_repo.get_profile = AsyncMock(return_value=None)
        profile_repo.default_profile = AsyncMock(
            return_value=UserPracticeProfile(user_id=pending.user_id, updated_at=datetime.now(UTC))
        )
        profile_repo.upsert_profile = AsyncMock()
        context_builder = AsyncMock()
        context_builder.build = AsyncMock(return_value=_built_context())
        plan_generator = AsyncMock()
        plan_generator.generate = AsyncMock(side_effect=PlanGenerationFailedError("bad draft"))
        use_case = GeneratePlanUseCase(
            plan_repo,
            profile_repo,
            context_builder,
            plan_generator,
            ExerciseValidator(),
        )

        await use_case.execute(
            PracticePlanJobMessage(
                job_id=uuid4(),
                plan_id=pending.plan_id,
                user_id=pending.user_id,
                source=PlanSource.MANUAL,
                request=PlanGenerationRequest(exercise_count=3),
                published_at=datetime.now(UTC),
            )
        )

        failed_update = plan_repo.update_plan.call_args_list[-1]
        assert failed_update.args[1]["status"] == PlanStatus.FAILED.value

    @pytest.mark.asyncio
    async def test_publishes_plan_ready_event_on_success(self) -> None:
        pending = _ready_plan(status=PlanStatus.PENDING)
        claimed = _ready_plan(status=PlanStatus.GENERATING, plan_id=pending.plan_id, user_id=pending.user_id)
        plan_repo = AsyncMock()
        plan_repo.get_plan_by_id = AsyncMock(return_value=pending)
        plan_repo.try_claim_plan_generation = AsyncMock(return_value=claimed)
        plan_repo.update_plan = AsyncMock()
        profile_repo = AsyncMock()
        profile_repo.get_profile = AsyncMock(return_value=None)
        profile_repo.default_profile = MagicMock(
            return_value=UserPracticeProfile(user_id=pending.user_id, updated_at=datetime.now(UTC))
        )
        profile_repo.upsert_profile = AsyncMock()
        context_builder = AsyncMock()
        context_builder.build = AsyncMock(return_value=_built_context())
        draft = sample_plan_draft()
        plan_generator = AsyncMock()
        plan_generator.generate = AsyncMock(return_value=draft)
        publisher = AsyncMock()
        use_case = GeneratePlanUseCase(
            plan_repo,
            profile_repo,
            context_builder,
            plan_generator,
            ExerciseValidator(),
            publisher,
            "practice-plan-ready-stream",
        )

        await use_case.execute(
            PracticePlanJobMessage(
                job_id=uuid4(),
                plan_id=pending.plan_id,
                user_id=pending.user_id,
                source=PlanSource.MANUAL,
                request=PlanGenerationRequest(exercise_count=3),
                published_at=datetime.now(UTC),
            )
        )

        publisher.publish.assert_awaited_once()
        queue_name, payload = publisher.publish.await_args.args
        assert queue_name == "practice-plan-ready-stream"
        assert str(pending.plan_id) in payload


class TestHandleInterviewCompletedUseCase:
    @pytest.mark.asyncio
    async def test_duplicate_session_id_is_idempotent(self) -> None:
        existing = _ready_plan(source=PlanSource.INTERVIEW, interview_session_id="sess-1")
        plan_repo = AsyncMock()
        plan_repo.get_plan_by_interview_session = AsyncMock(return_value=existing)
        use_case = HandleInterviewCompletedUseCase(
            plan_repo,
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
            "queue",
        )

        result = await use_case.execute(
            InterviewCompletedEvent(
                event_id=uuid4(),
                user_id=existing.user_id,
                session_id="sess-1",
                published_at=datetime.now(UTC),
            )
        )

        assert result is False
        plan_repo.create_plan.assert_not_called()

    @pytest.mark.asyncio
    async def test_retries_interview_report_lookup(self, monkeypatch) -> None:
        plan_repo = AsyncMock()
        plan_repo.get_plan_by_interview_session = AsyncMock(return_value=None)
        plan_repo.create_plan = AsyncMock()
        profile_repo = MagicMock()
        profile_repo.get_profile = AsyncMock(return_value=None)
        profile_repo.default_profile = _default_profile
        profile_repo.upsert_profile = AsyncMock()
        context_reader = AsyncMock()
        report = InterviewReport(summary="Done", weaknesses=["Redis"], skill_scores=[])
        from src.infrastructure.mongo.context_reader import InterviewContextData

        interview = InterviewContextData(session_id="sess-2", cv_correlation_id=None, report=report)
        context_reader.get_interview_by_session = AsyncMock(side_effect=[None, interview])
        context_builder = AsyncMock()
        context_builder.build = AsyncMock(return_value=_built_context())
        publisher = AsyncMock()
        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        monkeypatch.setattr("src.application.use_cases.worker_use_cases.asyncio.sleep", fake_sleep)
        monkeypatch.setattr(
            "src.application.use_cases.worker_use_cases.settings.practice_settings.interview_report_retry_seconds",
            2.0,
        )
        use_case = HandleInterviewCompletedUseCase(
            plan_repo,
            profile_repo,
            context_builder,
            context_reader,
            publisher,
            "queue",
        )

        result = await use_case.execute(
            InterviewCompletedEvent(
                event_id=uuid4(),
                user_id=uuid4(),
                session_id="sess-2",
                published_at=datetime.now(UTC),
            )
        )

        assert result is True
        assert sleeps == [2.0]
        assert context_reader.get_interview_by_session.await_count == 2

    @pytest.mark.asyncio
    async def test_duplicate_key_on_create_is_idempotent(self) -> None:
        plan_repo = AsyncMock()
        plan_repo.get_plan_by_interview_session = AsyncMock(return_value=None)
        plan_repo.create_plan = AsyncMock(side_effect=DuplicateKeyError("dup"))
        profile_repo = MagicMock()
        profile_repo.get_profile = AsyncMock(return_value=None)
        profile_repo.default_profile = _default_profile
        profile_repo.upsert_profile = AsyncMock()
        context_reader = AsyncMock()
        from src.infrastructure.mongo.context_reader import InterviewContextData

        context_reader.get_interview_by_session = AsyncMock(
            return_value=InterviewContextData(
                session_id="sess-3",
                cv_correlation_id=None,
                report=InterviewReport(summary="x"),
            )
        )
        context_builder = AsyncMock()
        context_builder.build = AsyncMock(return_value=_built_context())
        use_case = HandleInterviewCompletedUseCase(
            plan_repo,
            profile_repo,
            context_builder,
            context_reader,
            AsyncMock(),
            "queue",
        )

        result = await use_case.execute(
            InterviewCompletedEvent(
                event_id=uuid4(),
                user_id=uuid4(),
                session_id="sess-3",
                published_at=datetime.now(UTC),
            )
        )

        assert result is False


class TestSubmitAttemptUseCase:
    @pytest.mark.asyncio
    async def test_plan_not_ready_raises(self) -> None:
        pending = _ready_plan(status=PlanStatus.PENDING)
        plan_repo = AsyncMock()
        plan_repo.get_plan = AsyncMock(return_value=pending)
        use_case = SubmitAttemptUseCase(plan_repo, AsyncMock(), AsyncMock(), AsyncMock())

        with pytest.raises(PlanNotReadyError):
            await use_case.execute(pending.user_id, pending.plan_id, "mcq-1", {"selected_choice_ids": ["a"]})

    @pytest.mark.asyncio
    async def test_already_attempted_raises(self) -> None:
        plan = _ready_plan()
        plan_repo = AsyncMock()
        plan_repo.get_plan = AsyncMock(return_value=plan)
        attempt_repo = AsyncMock()
        attempt_repo.get_attempt = AsyncMock(return_value=object())
        use_case = SubmitAttemptUseCase(plan_repo, attempt_repo, AsyncMock(), AsyncMock())

        with pytest.raises(AlreadyAttemptedError):
            await use_case.execute(plan.user_id, plan.plan_id, "mcq-1", {"selected_choice_ids": ["a"]})

    @pytest.mark.asyncio
    async def test_flashcard_reveals_reference_answer(self) -> None:
        plan = _ready_plan()
        plan_repo = AsyncMock()
        plan_repo.get_plan = AsyncMock(return_value=plan)
        attempt_repo = AsyncMock()
        attempt_repo.get_attempt = AsyncMock(return_value=None)
        attempt_repo.upsert_attempt = AsyncMock()
        profile_repo = AsyncMock()
        profile_repo.get_profile = AsyncMock(return_value=None)
        grader = MagicMock()
        grader.grade_flashcard = AnswerGrader.grade_flashcard
        use_case = SubmitAttemptUseCase(plan_repo, attempt_repo, profile_repo, grader)

        attempt, reference_answer, explanation = await use_case.execute(
            plan.user_id,
            plan.plan_id,
            "flash-1",
            {"flashcard_rating": FlashcardRating.GOOD.value},
        )

        assert reference_answer == "Consistency, Availability, Partition tolerance"
        assert explanation is None
        assert attempt.exercise_id == "flash-1"
