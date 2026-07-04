import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pymongo.errors import DuplicateKeyError
from shared_models.practice.attempt import AttemptStatus, ExerciseAttempt
from shared_models.practice.exercise import ExerciseType, FlashcardRating
from shared_models.practice.messaging import PlanGenerationRequest, PlanSource, PracticePlanJobMessage
from shared_models.practice.plan import PlanStatus, PracticePlan
from src.agent.answer_grader import AnswerGrader
from src.agent.plan_generator import PlanGenerator
from src.application.services.plan_context_builder import PlanContextBuilder
from src.application.services.practice_services import ExerciseValidator, StreakService
from src.config import settings
from src.domain.exceptions.practice_errors import (
    AlreadyAttemptedError,
    AnswerTooLongError,
    GradingFailedError,
    InvalidAnswerFormatError,
    PlanGenerationFailedError,
    PlanNotFoundError,
    PlanNotReadyError,
)
from src.domain.interfaces.message_publisher import IMessagePublisher
from src.logger import app_logger


class GeneratePlanUseCase:
    def __init__(
        self,
        plan_repository,
        profile_repository,
        context_builder: PlanContextBuilder,
        plan_generator: PlanGenerator,
        validator: ExerciseValidator,
    ) -> None:
        self._plans = plan_repository
        self._profiles = profile_repository
        self._context_builder = context_builder
        self._plan_generator = plan_generator
        self._validator = validator

    async def execute(self, message: PracticePlanJobMessage) -> None:
        plan = await self._plans.get_plan_by_id(str(message.plan_id))
        if plan is None:
            raise PlanNotFoundError(f"Plan {message.plan_id} not found")

        if plan.status in {PlanStatus.READY, PlanStatus.GENERATING, PlanStatus.FAILED}:
            app_logger.info(
                "Skipping plan generation for %s: status already %s",
                message.plan_id,
                plan.status.value,
            )
            return

        claimed = await self._plans.try_claim_plan_generation(str(message.plan_id))
        if claimed is None:
            app_logger.info(
                "Skipping plan generation for %s: could not claim pending status",
                message.plan_id,
            )
            return

        profile = await self._profiles.get_profile(str(message.user_id))
        if profile is None:
            profile = self._profiles.default_profile(message.user_id)
            await self._profiles.upsert_profile(profile)

        built = await self._context_builder.build(
            str(message.user_id),
            message.request,
            profile,
            interview_session_id=message.interview_session_id,
        )
        await self._plans.update_plan(
            str(message.plan_id),
            {"context_snapshot": built.context_snapshot.model_dump(mode="json")},
        )

        last_error: Exception | None = None
        for _ in range(settings.practice_settings.max_generation_retries + 1):
            try:
                draft = await self._plan_generator.generate(built)
                self._validator.validate(draft, expected_count=message.request.exercise_count)
                ready_at = datetime.now(UTC)
                await self._plans.update_plan(
                    str(message.plan_id),
                    {
                        "status": PlanStatus.READY.value,
                        "title": draft.title,
                        "focus_skills": draft.focus_skills,
                        "exercises": [exercise.model_dump(mode="json") for exercise in draft.exercises],
                        "exercise_count": len(draft.exercises),
                        "updated_at": ready_at.isoformat(),
                        "ready_at": ready_at.isoformat(),
                        "error_code": None,
                        "error_message": None,
                    },
                )
                return
            except PlanGenerationFailedError as exc:
                last_error = exc
                app_logger.warning("Plan generation validation failed for %s: %s", message.plan_id, exc)

        failed_at = datetime.now(UTC)
        await self._plans.update_plan(
            str(message.plan_id),
            {
                "status": PlanStatus.FAILED.value,
                "error_code": "PLAN_GENERATION_FAILED",
                "error_message": str(last_error) if last_error else "Unknown generation failure",
                "updated_at": failed_at.isoformat(),
            },
        )


class HandleInterviewCompletedUseCase:
    def __init__(
        self,
        plan_repository,
        profile_repository,
        context_builder: PlanContextBuilder,
        context_reader,
        publisher: IMessagePublisher,
        plan_queue_name: str,
    ) -> None:
        self._plans = plan_repository
        self._profiles = profile_repository
        self._context_builder = context_builder
        self._context_reader = context_reader
        self._publisher = publisher
        self._plan_queue_name = plan_queue_name

    async def execute(self, event) -> bool:
        # Interview-triggered auto-plans do not consume daily_plan_quota (post-interview UX).
        existing = await self._plans.get_plan_by_interview_session(event.session_id)
        if existing is not None:
            return False

        interview = await self._context_reader.get_interview_by_session(event.session_id)
        if interview is None:
            await asyncio.sleep(settings.practice_settings.interview_report_retry_seconds)
            interview = await self._context_reader.get_interview_by_session(event.session_id)
        if interview is None:
            app_logger.warning("Interview report not found for session %s", event.session_id)
            return False

        profile = await self._profiles.get_profile(str(event.user_id))
        if profile is None:
            profile = self._profiles.default_profile(event.user_id)
            await self._profiles.upsert_profile(profile)

        request = PlanGenerationRequest(
            difficulty=profile.preferred_difficulty,
            exercise_types=profile.preferred_exercise_types
            or [
                ExerciseType.MCQ_SINGLE,
                ExerciseType.OPEN_QUESTION,
                ExerciseType.FLASHCARD,
            ],
            exercise_count=settings.practice_settings.default_exercise_count,
            include_interview_context=True,
            include_cv_context=True,
        )
        built = await self._context_builder.build(
            str(event.user_id),
            request,
            profile,
            interview_session_id=event.session_id,
        )

        now = datetime.now(UTC)
        plan = PracticePlan(
            plan_id=uuid4(),
            user_id=event.user_id,
            source=PlanSource.INTERVIEW,
            status=PlanStatus.PENDING,
            title="Post-interview practice plan",
            focus_skills=built.focus_skills,
            difficulty=built.context_snapshot.difficulty,
            context_snapshot=built.context_snapshot,
            interview_session_id=event.session_id,
            cv_correlation_id=event.cv_correlation_id,
            created_at=now,
            updated_at=now,
        )
        try:
            await self._plans.create_plan(plan)
        except DuplicateKeyError:
            app_logger.info("Plan already exists for interview session %s", event.session_id)
            return False

        message = PracticePlanJobMessage(
            job_id=uuid4(),
            plan_id=plan.plan_id,
            user_id=event.user_id,
            source=PlanSource.INTERVIEW,
            request=request,
            interview_session_id=event.session_id,
            cv_correlation_id=event.cv_correlation_id,
            published_at=now,
        )
        await self._publisher.publish(self._plan_queue_name, message.model_dump_json())
        return True


class SubmitAttemptUseCase:
    def __init__(
        self,
        plan_repository,
        attempt_repository,
        profile_repository,
        answer_grader: AnswerGrader,
    ) -> None:
        self._plans = plan_repository
        self._attempts = attempt_repository
        self._profiles = profile_repository
        self._grader = answer_grader

    async def execute(
        self,
        user_id: UUID,
        plan_id: UUID,
        exercise_id: str,
        answer_payload: dict,
    ) -> tuple[ExerciseAttempt, str | None, str | None]:
        plan = await self._plans.get_plan(str(plan_id), str(user_id))
        if plan is None:
            raise PlanNotFoundError("Plan not found")
        if plan.status != PlanStatus.READY:
            raise PlanNotReadyError()

        existing = await self._attempts.get_attempt(str(user_id), str(plan_id), exercise_id)
        if existing is not None:
            raise AlreadyAttemptedError()

        exercise = AnswerGrader.find_exercise(plan, exercise_id)
        if exercise is None:
            raise PlanNotFoundError("Exercise not found")

        now = datetime.now(UTC)
        grading = await self._grade_exercise(exercise, answer_payload)
        attempt = ExerciseAttempt(
            attempt_id=uuid4(),
            plan_id=plan_id,
            exercise_id=exercise_id,
            user_id=user_id,
            exercise_type=exercise.type,
            answer=answer_payload,
            flashcard_rating=answer_payload.get("flashcard_rating"),
            status=AttemptStatus.GRADED,
            grading=grading,
            submitted_at=now,
            graded_at=now,
        )
        await self._attempts.upsert_attempt(attempt)

        profile = await self._profiles.get_profile(str(user_id))
        if profile is not None:
            profile.total_exercises_completed += 1
            profile = StreakService.update_on_completion(profile)
            profile.updated_at = datetime.now(UTC)
            await self._profiles.upsert_profile(profile)

        reference_answer: str | None = None
        explanation: str | None = None
        if exercise.type in {ExerciseType.MCQ_SINGLE, ExerciseType.MCQ_MULTI}:
            explanation = exercise.explanation
        elif exercise.type in {ExerciseType.OPEN_QUESTION, ExerciseType.FLASHCARD}:
            reference_answer = exercise.reference_answer
        return attempt, reference_answer, explanation

    async def _grade_exercise(self, exercise, answer_payload: dict):
        if exercise.type == ExerciseType.MCQ_SINGLE:
            selected = answer_payload.get("selected_choice_ids")
            if not isinstance(selected, list):
                raise InvalidAnswerFormatError("MCQ requires selected_choice_ids list")
            return self._grader.grade_mcq_single(exercise, selected)
        if exercise.type == ExerciseType.MCQ_MULTI:
            selected = answer_payload.get("selected_choice_ids")
            if not isinstance(selected, list):
                raise InvalidAnswerFormatError("MCQ requires selected_choice_ids list")
            return self._grader.grade_mcq_multi(exercise, selected)
        if exercise.type == ExerciseType.OPEN_QUESTION:
            text_answer = answer_payload.get("text_answer")
            if not isinstance(text_answer, str) or not text_answer.strip():
                raise InvalidAnswerFormatError("Open question requires text_answer")
            if exercise.max_answer_chars and len(text_answer) > exercise.max_answer_chars:
                raise AnswerTooLongError()
            try:
                return await self._grader.grade_open_question(exercise, text_answer)
            except Exception as exc:
                raise GradingFailedError() from exc
        if exercise.type == ExerciseType.FLASHCARD:
            rating_value = answer_payload.get("flashcard_rating")
            if rating_value is None:
                raise InvalidAnswerFormatError("Flashcard requires flashcard_rating")
            rating = FlashcardRating(rating_value)
            return self._grader.grade_flashcard(rating)
        raise InvalidAnswerFormatError(f"Unsupported exercise type: {exercise.type.value}")


class GetProgressUseCase:
    def __init__(self, plan_repository, attempt_repository, profile_repository) -> None:
        self._plans = plan_repository
        self._attempts = attempt_repository
        self._profiles = profile_repository

    async def execute(self, user_id: UUID, plan_id: UUID) -> dict | None:
        plan = await self._plans.get_plan(str(plan_id), str(user_id))
        if plan is None:
            return None
        attempts = await self._attempts.list_plan_attempts(str(user_id), str(plan_id))
        profile = await self._profiles.get_profile(str(user_id))

        completed = sum(1 for attempt in attempts if attempt.status == AttemptStatus.GRADED)
        skipped = sum(1 for attempt in attempts if attempt.status == AttemptStatus.SKIPPED)
        scores = [attempt.grading.score for attempt in attempts if attempt.grading is not None]
        average_score = round(sum(scores) / len(scores), 1) if scores else 0.0

        scores_by_skill: dict[str, dict[str, float | int]] = {}
        exercise_map = {exercise.exercise_id: exercise for exercise in plan.exercises}
        for attempt in attempts:
            if attempt.grading is None:
                continue
            exercise = exercise_map.get(attempt.exercise_id)
            if not exercise:
                continue
            for skill in exercise.skill_tags:
                bucket = scores_by_skill.setdefault(skill, {"total": 0.0, "count": 0})
                bucket["total"] += attempt.grading.score
                bucket["count"] += 1

        return {
            "plan_id": str(plan_id),
            "total_exercises": plan.exercise_count or len(plan.exercises),
            "attempted": len(attempts),
            "completed": completed,
            "skipped": skipped,
            "completion_percent": round((completed / max(plan.exercise_count, 1)) * 100, 1),
            "average_score": average_score,
            "scores_by_skill": {
                skill: {"average": round(values["total"] / values["count"], 1), "count": values["count"]}
                for skill, values in scores_by_skill.items()
            },
            "current_streak_days": profile.current_streak_days if profile else 0,
        }
