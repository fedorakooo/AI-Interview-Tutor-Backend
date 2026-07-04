from datetime import UTC, datetime
from uuid import UUID, uuid4

from shared_models.practice.messaging import PlanGenerationRequest, PlanSource, PracticePlanJobMessage
from shared_models.practice.plan import PlanStatus, PracticePlan
from src.application.services.plan_context_builder import PlanContextBuilder
from src.application.services.practice_services import QuotaService
from src.config import settings
from src.domain.exceptions.practice_errors import (
    InvalidExerciseCountError,
    UnsupportedExerciseTypeError,
)
from src.domain.interfaces.message_publisher import IMessagePublisher


class RequestPlanUseCase:
    def __init__(
        self,
        plan_repository,
        profile_repository,
        context_builder: PlanContextBuilder,
        quota_service: QuotaService,
        publisher: IMessagePublisher,
        plan_queue_name: str,
    ) -> None:
        self._plans = plan_repository
        self._profiles = profile_repository
        self._context_builder = context_builder
        self._quota_service = quota_service
        self._publisher = publisher
        self._plan_queue_name = plan_queue_name

    async def execute(self, user_id: UUID, request: PlanGenerationRequest) -> PracticePlan:
        self._validate_request(request)
        profile = await self._profiles.get_profile(str(user_id))
        if profile is None:
            profile = self._profiles.default_profile(user_id)
            await self._profiles.upsert_profile(profile)

        profile = await self._quota_service.check_and_increment(profile)
        built = await self._context_builder.build(str(user_id), request, profile)

        now = datetime.now(UTC)
        plan = PracticePlan(
            plan_id=uuid4(),
            user_id=user_id,
            source=PlanSource(built.source),
            status=PlanStatus.PENDING,
            title=request.title_hint or "Practice Plan",
            focus_skills=built.focus_skills,
            difficulty=built.context_snapshot.difficulty,
            context_snapshot=built.context_snapshot,
            interview_session_id=built.interview_session_id,
            cv_correlation_id=built.cv_correlation_id,
            created_at=now,
            updated_at=now,
        )
        await self._plans.create_plan(plan)
        profile.updated_at = datetime.now(UTC)
        await self._profiles.upsert_profile(profile)

        message = PracticePlanJobMessage(
            job_id=uuid4(),
            plan_id=plan.plan_id,
            user_id=user_id,
            source=plan.source,
            request=request,
            interview_session_id=built.interview_session_id,
            cv_correlation_id=built.cv_correlation_id,
            published_at=now,
        )
        await self._publisher.publish(self._plan_queue_name, message.model_dump_json())
        return plan

    @staticmethod
    def _validate_request(request: PlanGenerationRequest) -> None:
        min_count = settings.practice_settings.min_exercise_count
        max_count = settings.practice_settings.max_exercises_per_plan
        if not (min_count <= request.exercise_count <= max_count):
            raise InvalidExerciseCountError()
        for exercise_type in request.exercise_types:
            if exercise_type.value not in settings.practice_settings.supported_exercise_types:
                raise UnsupportedExerciseTypeError(exercise_type.value)


class GetPlanUseCase:
    def __init__(self, plan_repository, sanitizer) -> None:
        self._plans = plan_repository
        self._sanitizer = sanitizer

    async def execute(self, user_id: UUID, plan_id: UUID, *, sanitize: bool = True) -> PracticePlan | None:
        plan = await self._plans.get_plan(str(plan_id), str(user_id))
        if plan is None:
            return None
        if sanitize and plan.status == PlanStatus.READY:
            plan.exercises = self._sanitizer.sanitize_plan_exercises(plan.exercises)
        return plan


class ListPlansUseCase:
    def __init__(self, plan_repository) -> None:
        self._plans = plan_repository

    async def execute(
        self,
        user_id: UUID,
        *,
        skip: int = 0,
        limit: int = 20,
        status: PlanStatus | None = None,
    ) -> list[PracticePlan]:
        return await self._plans.list_plans(str(user_id), skip=skip, limit=limit, status=status)


class ArchivePlanUseCase:
    def __init__(self, plan_repository) -> None:
        self._plans = plan_repository

    async def execute(self, user_id: UUID, plan_id: UUID) -> bool:
        plan = await self._plans.get_plan(str(plan_id), str(user_id))
        if plan is None:
            return False
        await self._plans.update_plan(
            str(plan_id),
            {"status": PlanStatus.ARCHIVED.value, "updated_at": datetime.now(UTC).isoformat()},
        )
        return True
