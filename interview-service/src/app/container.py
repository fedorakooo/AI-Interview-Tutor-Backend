from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from jwt_handler.handlers import CandidateInterviewTokenVerifier
from jwt_handler.interfaces import ICandidateInterviewTokenVerifier
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from redis.asyncio import Redis
from src.agents.answer_evaluator.agent import AnswerEvaluator
from src.agents.assessment_writer.agent import AssessmentTextWriter
from src.agents.feedback_writer.agent import FeedbackWriter
from src.agents.interviewer.agent import InterviewerAgent
from src.agents.models import parse_model_specs
from src.agents.spec_drafter.agent import SpecDrafter
from src.application.interfaces.assessment_report_service import IAssessmentReportService
from src.application.interfaces.candidate_feedback_service import ICandidateFeedbackService
from src.application.interfaces.data_erasure_service import IDataErasureService
from src.application.interfaces.interview_session_service import IInterviewSessionService
from src.application.interfaces.template_draft_service import ITemplateDraftService
from src.application.services.assessment_report_service import AssessmentReportService
from src.application.services.candidate_feedback_service import CandidateFeedbackService
from src.application.services.completion_outbox_dispatcher import CompletionOutboxDispatcher
from src.application.services.completion_publisher import CompletionPublisher
from src.application.services.cv_loader import CvLoader
from src.application.services.data_erasure_service import DataErasureService
from src.application.services.evidence_recorder import EvidenceRecorder
from src.application.services.interview_session_service import InterviewSessionService
from src.application.services.interviewer_turn import InterviewerTurn
from src.application.services.report_loader import ReportLoader
from src.application.services.template_draft_service import TemplateDraftService
from src.config import settings
from src.domain.interfaces.ai.answer_evaluator import IAnswerEvaluator
from src.domain.interfaces.ai.assessment_text_writer import IAssessmentTextWriter
from src.domain.interfaces.ai.feedback_writer import IFeedbackWriter
from src.domain.interfaces.ai.interviewer_agent import IInterviewerAgent
from src.domain.interfaces.ai.spec_drafter import ISpecDrafter
from src.domain.interfaces.clients.assessment_context_client import IAssessmentContextClient
from src.domain.interfaces.messaging.assessment_completed_publisher import IAssessmentCompletedPublisher
from src.domain.interfaces.repositories.assessment_repository import IAssessmentRepository
from src.domain.interfaces.repositories.attempt_data_repository import IAttemptDataRepository
from src.domain.interfaces.repositories.candidate_cv_repository import ICandidateCvRepository
from src.domain.interfaces.repositories.completion_outbox_repository import ICompletionOutboxRepository
from src.domain.interfaces.repositories.feedback_repository import IFeedbackRepository
from src.domain.interfaces.repositories.interview_event_repository import IInterviewEventRepository
from src.domain.interfaces.session.session_lock import ISessionLock
from src.domain.interfaces.session.session_presence import ISessionPresence
from src.infrastructure.jwt.attempt_token_verifier import AttemptTokenVerifier
from src.infrastructure.mongo.indexed_repository import IndexedRepository
from src.infrastructure.mongo.repositories.assessment_repository import AssessmentRepository
from src.infrastructure.mongo.repositories.attempt_data_repository import AttemptDataRepository
from src.infrastructure.mongo.repositories.candidate_cv_repository import CandidateCvRepository
from src.infrastructure.mongo.repositories.completion_outbox_repository import CompletionOutboxRepository
from src.infrastructure.mongo.repositories.feedback_repository import FeedbackRepository
from src.infrastructure.mongo.repositories.interview_event_repository import InterviewEventRepository
from src.infrastructure.rabbitmq.assessment_completed_publisher import AssessmentCompletedPublisher
from src.infrastructure.redis.session_lock import SessionLock
from src.infrastructure.redis.session_presence import SessionPresence
from src.infrastructure.user_management.assessment_context_client import AssessmentContextClient


@dataclass
class AppContainer:
    interview_session_service: IInterviewSessionService
    assessment_report_service: IAssessmentReportService
    candidate_feedback_service: ICandidateFeedbackService
    template_draft_service: ITemplateDraftService
    data_erasure_service: IDataErasureService
    completion_dispatcher: CompletionOutboxDispatcher
    completed_publisher: IAssessmentCompletedPublisher
    indexed_repositories: list[IndexedRepository]


def build_container(
    mongo_client: AsyncIOMotorClient,
    redis_client: Redis,
    http_client: httpx.AsyncClient,
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

    def collection(name: str) -> AsyncIOMotorCollection:
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
    cv_repository = cv_repository or CandidateCvRepository(collection(mongo_settings.cv_analysis_collection_name))
    lock = lock or SessionLock(redis_client)
    presence = presence or SessionPresence(redis_client)
    evaluator = evaluator or AnswerEvaluator(parse_model_specs(settings.interview_evaluator_models))
    interviewer = interviewer or InterviewerAgent(parse_model_specs(settings.interview_interviewer_models))
    assessment_text_writer = assessment_text_writer or AssessmentTextWriter(
        parse_model_specs(settings.interview_report_models)
    )
    feedback_writer = feedback_writer or FeedbackWriter(parse_model_specs(settings.interview_feedback_models))
    spec_drafter = spec_drafter or SpecDrafter(parse_model_specs(settings.interview_spec_models))
    completed_publisher = completed_publisher or AssessmentCompletedPublisher(
        amqp_url=settings.rabbitmq_settings.url,
        queue_name=settings.rabbitmq_settings.assessment_completed_queue_name,
    )
    user_management = settings.user_management_settings
    context_client = context_client or AssessmentContextClient(
        client=http_client,
        base_url=user_management.url,
        service_token=user_management.internal_service_token,
    )
    token_verifier = token_verifier or CandidateInterviewTokenVerifier(public_key=settings.jwt_settings.public_key)

    completion_publisher = CompletionPublisher(completion_outbox_repository, completed_publisher, clock)
    cv_loader = CvLoader(cv_repository)
    report_loader = ReportLoader(event_repository, assessment_repository, assessment_text_writer, clock)

    indexed_repositories = [
        repository
        for repository in (event_repository, assessment_repository, feedback_repository, completion_outbox_repository)
        if isinstance(repository, IndexedRepository)
    ]

    return AppContainer(
        interview_session_service=InterviewSessionService(
            AttemptTokenVerifier(token_verifier),
            context_client,
            lock,
            presence,
            event_repository,
            cv_loader,
            EvidenceRecorder(event_repository, evaluator, clock),
            InterviewerTurn(event_repository, interviewer, cv_loader, completion_publisher, clock),
            completion_publisher,
            clock,
        ),
        assessment_report_service=AssessmentReportService(report_loader, assessment_repository, context_client, clock),
        candidate_feedback_service=CandidateFeedbackService(
            report_loader, feedback_repository, feedback_writer, context_client, clock
        ),
        template_draft_service=TemplateDraftService(spec_drafter),
        data_erasure_service=DataErasureService(lock, attempt_data_repository),
        completion_dispatcher=CompletionOutboxDispatcher(completion_outbox_repository, completed_publisher),
        completed_publisher=completed_publisher,
        indexed_repositories=indexed_repositories,
    )
