from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from jwt_handler.handlers import CandidateInterviewTokenVerifier
from jwt_handler.interfaces import ICandidateInterviewTokenVerifier
from src.application.services.assessment_report_service import AssessmentReportService
from src.application.services.interview_turn_service import InterviewTurnService
from src.application.use_cases.assessment_reports import (
    AddFocusReviewUseCase,
    GetAssessmentOverviewUseCase,
    GetFocusDetailUseCase,
)
from src.application.use_cases.candidate_feedback import EditCandidateFeedbackUseCase, GetCandidateFeedbackUseCase
from src.application.use_cases.data_erasure import EraseAttemptDataUseCase
from src.application.use_cases.interview_session import (
    HandleCandidateAnswerUseCase,
    ListInterviewEventsUseCase,
    OpenInterviewSessionUseCase,
    PauseInterviewSessionUseCase,
    RegisterInterviewConnectionUseCase,
)
from src.application.use_cases.open_interview_connection import OpenInterviewConnectionUseCase
from src.application.use_cases.template_drafts import CreateTemplateDraftUseCase
from src.config import settings
from src.domain.interfaces.answer_evaluator import IAnswerEvaluator
from src.domain.interfaces.assessment_completed_publisher import IAssessmentCompletedPublisher
from src.domain.interfaces.assessment_context_client import IAssessmentContextClient
from src.domain.interfaces.assessment_repository import IAssessmentRepository
from src.domain.interfaces.assessment_text_writer import IAssessmentTextWriter
from src.domain.interfaces.attempt_data_repository import IAttemptDataRepository
from src.domain.interfaces.candidate_cv_repository import ICandidateCvRepository
from src.domain.interfaces.completion_outbox_repository import ICompletionOutboxRepository
from src.domain.interfaces.feedback_repository import IFeedbackRepository
from src.domain.interfaces.feedback_writer import IFeedbackWriter
from src.domain.interfaces.interview_event_repository import IInterviewEventRepository
from src.domain.interfaces.interviewer_agent import IInterviewerAgent
from src.domain.interfaces.session_lock import ISessionLock
from src.domain.interfaces.session_presence import ISessionPresence
from src.domain.interfaces.spec_drafter import ISpecDrafter
from src.infrastructure.ai.assessment_writer import PydanticAssessmentTextWriter
from src.infrastructure.ai.evaluator import PydanticAnswerEvaluator
from src.infrastructure.ai.feedback_writer import PydanticFeedbackWriter
from src.infrastructure.ai.interviewer import PydanticInterviewerAgent
from src.infrastructure.ai.models import parse_model_specs
from src.infrastructure.ai.spec_agent import PydanticSpecDrafter
from src.infrastructure.jwt.attempt_token_verifier import AttemptTokenVerifier
from src.infrastructure.mongo.repositories.assessment_repository import AssessmentRepository
from src.infrastructure.mongo.repositories.attempt_data_repository import AttemptDataRepository
from src.infrastructure.mongo.repositories.candidate_cv_repository import CandidateCvRepository
from src.infrastructure.mongo.repositories.completion_outbox_repository import CompletionOutboxRepository
from src.infrastructure.mongo.repositories.feedback_repository import FeedbackRepository
from src.infrastructure.mongo.repositories.interview_event_repository import InterviewEventRepository
from src.infrastructure.mongo.repository import MongoRepository
from src.infrastructure.rabbitmq.assessment_completed_publisher import AssessmentCompletedPublisher
from src.infrastructure.rabbitmq.completion_outbox_dispatcher import CompletionOutboxDispatcher
from src.infrastructure.redis.session_lock import RedisSessionLock
from src.infrastructure.redis.session_presence import RedisSessionPresence
from src.infrastructure.user_management.assessment_context_client import UserManagementAssessmentContextClient


@dataclass
class AppContainer:
    open_interview_connection_use_case: OpenInterviewConnectionUseCase
    list_interview_events_use_case: ListInterviewEventsUseCase
    register_interview_connection_use_case: RegisterInterviewConnectionUseCase
    open_interview_session_use_case: OpenInterviewSessionUseCase
    handle_candidate_answer_use_case: HandleCandidateAnswerUseCase
    pause_interview_session_use_case: PauseInterviewSessionUseCase
    get_assessment_overview_use_case: GetAssessmentOverviewUseCase
    get_focus_detail_use_case: GetFocusDetailUseCase
    add_focus_review_use_case: AddFocusReviewUseCase
    get_candidate_feedback_use_case: GetCandidateFeedbackUseCase
    edit_candidate_feedback_use_case: EditCandidateFeedbackUseCase
    create_template_draft_use_case: CreateTemplateDraftUseCase
    erase_attempt_data_use_case: EraseAttemptDataUseCase
    assessment_context_client: IAssessmentContextClient
    completion_dispatcher: CompletionOutboxDispatcher
    completed_publisher: IAssessmentCompletedPublisher
    indexed_repositories: list


def build_container(
    mongo_client,
    redis_client,
    http_client,
    *,
    event_repository: IInterviewEventRepository | None = None,
    assessment_repository: IAssessmentRepository | None = None,
    feedback_repository: IFeedbackRepository | None = None,
    completion_outbox_repository: ICompletionOutboxRepository | None = None,
    attempt_data_repository: IAttemptDataRepository | None = None,
    cv_repository: ICandidateCvRepository | None = None,
    lock: ISessionLock | None = None,
    presence: ISessionPresence | None = None,
    evaluator: IAnswerEvaluator | None = None,
    interviewer: IInterviewerAgent | None = None,
    assessment_text_writer: IAssessmentTextWriter | None = None,
    feedback_writer: IFeedbackWriter | None = None,
    spec_drafter: ISpecDrafter | None = None,
    completed_publisher: IAssessmentCompletedPublisher | None = None,
    context_client: IAssessmentContextClient | None = None,
    token_verifier: ICandidateInterviewTokenVerifier | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> AppContainer:
    mongo_settings = settings.mongo_settings

    def collection(name: str):
        return mongo_client[mongo_settings.db_name][name]

    event_repository = event_repository or InterviewEventRepository(
        collection(mongo_settings.interview_events_collection_name)
    )
    assessment_repository = assessment_repository or AssessmentRepository(
        collection(mongo_settings.interview_assessments_collection_name),
        collection(mongo_settings.interview_assessment_reviews_collection_name),
    )
    feedback_repository = feedback_repository or FeedbackRepository(
        collection(mongo_settings.interview_feedback_collection_name)
    )
    completion_outbox_repository = completion_outbox_repository or CompletionOutboxRepository(
        collection(mongo_settings.interview_completion_outbox_collection_name)
    )
    attempt_data_repository = attempt_data_repository or AttemptDataRepository(
        events=collection(mongo_settings.interview_events_collection_name),
        assessments=collection(mongo_settings.interview_assessments_collection_name),
        reviews=collection(mongo_settings.interview_assessment_reviews_collection_name),
        feedback=collection(mongo_settings.interview_feedback_collection_name),
        cv_documents=collection(mongo_settings.cv_analysis_collection_name),
    )
    cv_repository = cv_repository or CandidateCvRepository(
        MongoRepository(
            client=mongo_client,
            db_name=mongo_settings.db_name,
            collection_name=mongo_settings.cv_analysis_collection_name,
        )
    )
    lock = lock or RedisSessionLock(redis_client)
    presence = presence or RedisSessionPresence(redis_client)
    evaluator = evaluator or PydanticAnswerEvaluator(parse_model_specs(settings.interview_evaluator_models))
    interviewer = interviewer or PydanticInterviewerAgent(parse_model_specs(settings.interview_interviewer_models))
    assessment_text_writer = assessment_text_writer or PydanticAssessmentTextWriter(
        parse_model_specs(settings.interview_report_models)
    )
    feedback_writer = feedback_writer or PydanticFeedbackWriter(parse_model_specs(settings.interview_feedback_models))
    spec_drafter = spec_drafter or PydanticSpecDrafter(parse_model_specs(settings.interview_spec_models))
    completed_publisher = completed_publisher or AssessmentCompletedPublisher(
        amqp_url=settings.rabbitmq_settings.url,
        queue_name=settings.rabbitmq_settings.assessment_completed_queue_name,
    )
    user_management = settings.user_management_settings
    context_client = context_client or UserManagementAssessmentContextClient(
        client=http_client,
        base_url=user_management.url,
        service_token=user_management.internal_service_token,
    )
    token_verifier = token_verifier or CandidateInterviewTokenVerifier(public_key=settings.jwt_settings.public_key)
    attempt_token_verifier = AttemptTokenVerifier(token_verifier)

    turn_service = InterviewTurnService(
        event_repository,
        evaluator,
        interviewer,
        cv_repository,
        completed_publisher,
        completion_outbox_repository,
        clock,
    )
    report_service = AssessmentReportService(event_repository, assessment_repository, assessment_text_writer, clock)
    get_feedback_use_case = GetCandidateFeedbackUseCase(report_service, feedback_repository, feedback_writer, clock)

    return AppContainer(
        open_interview_connection_use_case=OpenInterviewConnectionUseCase(attempt_token_verifier, context_client),
        list_interview_events_use_case=ListInterviewEventsUseCase(event_repository),
        register_interview_connection_use_case=RegisterInterviewConnectionUseCase(presence),
        open_interview_session_use_case=OpenInterviewSessionUseCase(lock, event_repository, turn_service),
        handle_candidate_answer_use_case=HandleCandidateAnswerUseCase(lock, event_repository, turn_service, clock),
        pause_interview_session_use_case=PauseInterviewSessionUseCase(lock, presence, event_repository, clock),
        get_assessment_overview_use_case=GetAssessmentOverviewUseCase(report_service),
        get_focus_detail_use_case=GetFocusDetailUseCase(report_service),
        add_focus_review_use_case=AddFocusReviewUseCase(report_service, assessment_repository, clock),
        get_candidate_feedback_use_case=get_feedback_use_case,
        edit_candidate_feedback_use_case=EditCandidateFeedbackUseCase(
            report_service, feedback_repository, get_feedback_use_case, clock
        ),
        create_template_draft_use_case=CreateTemplateDraftUseCase(spec_drafter),
        erase_attempt_data_use_case=EraseAttemptDataUseCase(lock, attempt_data_repository),
        assessment_context_client=context_client,
        completion_dispatcher=CompletionOutboxDispatcher(completion_outbox_repository, completed_publisher),
        completed_publisher=completed_publisher,
        indexed_repositories=[
            repository
            for repository in (
                event_repository,
                assessment_repository,
                feedback_repository,
                completion_outbox_repository,
            )
            if hasattr(repository, "ensure_indexes")
        ],
    )
