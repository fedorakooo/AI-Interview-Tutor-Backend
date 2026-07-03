from dataclasses import dataclass
from uuid import UUID

from src.agent.answer_grader import AnswerGrader
from src.agent.plan_generator import PlanGenerator
from src.application.services.plan_context_builder import PlanContextBuilder
from src.application.services.practice_services import ExerciseSanitizer, ExerciseValidator, QuotaService
from src.application.use_cases.plan_use_cases import (
    ArchivePlanUseCase,
    GetPlanUseCase,
    ListPlansUseCase,
    RequestPlanUseCase,
)
from src.application.use_cases.profile_use_cases import GetProfileUseCase, UpdateProfileUseCase
from src.application.use_cases.worker_use_cases import GeneratePlanUseCase, GetProgressUseCase, SubmitAttemptUseCase
from src.config import settings
from src.infrastructure.mongo.context_reader import ContextReader
from src.infrastructure.mongo.repositories import AttemptRepository, PlanRepository, ProfileRepository
from src.infrastructure.rabbitmq.publisher import RabbitMQPublisher


@dataclass
class AppContainer:
    get_profile_use_case: GetProfileUseCase
    update_profile_use_case: UpdateProfileUseCase
    request_plan_use_case: RequestPlanUseCase
    get_plan_use_case: GetPlanUseCase
    list_plans_use_case: ListPlansUseCase
    archive_plan_use_case: ArchivePlanUseCase
    submit_attempt_use_case: SubmitAttemptUseCase
    get_progress_use_case: GetProgressUseCase
    attempt_repository: AttemptRepository
    mongo_client: object


def build_container(mongo_client) -> AppContainer:
    plan_repository = PlanRepository(mongo_client)
    attempt_repository = AttemptRepository(mongo_client)
    profile_repository = ProfileRepository(mongo_client)
    context_reader = ContextReader(mongo_client)
    context_builder = PlanContextBuilder(context_reader)
    publisher = RabbitMQPublisher(settings.rabbitmq_settings.url)
    sanitizer = ExerciseSanitizer()
    validator = ExerciseValidator()
    quota_service = QuotaService(profile_repository)
    plan_generator = PlanGenerator()
    answer_grader = AnswerGrader()

    generate_plan_use_case = GeneratePlanUseCase(
        plan_repository,
        profile_repository,
        context_builder,
        plan_generator,
        validator,
    )

    from src.application.use_cases.worker_use_cases import HandleInterviewCompletedUseCase

    handle_interview_use_case = HandleInterviewCompletedUseCase(
        plan_repository,
        profile_repository,
        context_builder,
        context_reader,
        publisher,
        settings.rabbitmq_settings.practice_plan_queue_name,
    )

    return (
        AppContainer(
            get_profile_use_case=GetProfileUseCase(profile_repository),
            update_profile_use_case=UpdateProfileUseCase(profile_repository),
            request_plan_use_case=RequestPlanUseCase(
                plan_repository,
                profile_repository,
                context_builder,
                quota_service,
                publisher,
                settings.rabbitmq_settings.practice_plan_queue_name,
            ),
            get_plan_use_case=GetPlanUseCase(plan_repository, sanitizer),
            list_plans_use_case=ListPlansUseCase(plan_repository),
            archive_plan_use_case=ArchivePlanUseCase(plan_repository),
            submit_attempt_use_case=SubmitAttemptUseCase(
                plan_repository,
                attempt_repository,
                profile_repository,
                answer_grader,
            ),
            get_progress_use_case=GetProgressUseCase(plan_repository, attempt_repository, profile_repository),
            attempt_repository=attempt_repository,
            mongo_client=mongo_client,
        ),
        generate_plan_use_case,
        handle_interview_use_case,
        plan_repository,
        attempt_repository,
        profile_repository,
    )


def get_user_id(payload) -> UUID:
    return UUID(payload["id"])
