from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from src.application.interview.completion_dispatcher import CompletionOutboxDispatcher
from src.application.interview.erasure_service import AttemptErasureService
from src.application.interview.feedback_service import CandidateFeedbackService
from src.application.interview.report_service import AssessmentReportService
from src.application.interview.session_service import InterviewSessionService
from src.application.interview.spec_service import SpecDraftService
from src.config import settings
from src.infrastructure.ai.assessment_writer import PydanticAssessmentTextWriter
from src.infrastructure.ai.evaluator import PydanticAnswerEvaluator
from src.infrastructure.ai.feedback_writer import PydanticFeedbackWriter
from src.infrastructure.ai.interviewer import PydanticInterviewerAgent
from src.infrastructure.ai.models import parse_model_specs
from src.infrastructure.ai.spec_agent import PydanticSpecDrafter
from src.infrastructure.mongo import MongoRepository
from src.infrastructure.mongo_assessment_store import MongoAssessmentStore
from src.infrastructure.mongo_attempt_data_eraser import MongoAttemptDataEraser
from src.infrastructure.mongo_candidate_cv_provider import MongoCandidateCvProvider
from src.infrastructure.mongo_completion_outbox import MongoCompletionOutbox
from src.infrastructure.mongo_event_journal import MongoEventJournal
from src.infrastructure.mongo_feedback_store import MongoFeedbackStore
from src.infrastructure.rabbitmq.assessment_completed_publisher import AssessmentCompletedPublisher
from src.infrastructure.redis.client import create_redis_client
from src.infrastructure.redis.session_lock import RedisSessionLock
from src.infrastructure.redis.session_presence import RedisSessionPresence
from src.infrastructure.user_management.assessment_context_client import UserManagementAssessmentContextClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    user_management = settings.user_management_settings
    mongo_settings = settings.mongo_settings
    mongo_client = AsyncIOMotorClient(mongo_settings.url)
    redis_client = create_redis_client()
    app.state.mongo_client = mongo_client
    app.state.redis_client = redis_client
    journal = MongoEventJournal(mongo_client[mongo_settings.db_name][mongo_settings.interview_events_collection_name])
    await journal.ensure_indexes()
    assessment_store = MongoAssessmentStore(
        mongo_client[mongo_settings.db_name][mongo_settings.interview_assessments_collection_name],
        mongo_client[mongo_settings.db_name][mongo_settings.interview_assessment_reviews_collection_name],
    )
    await assessment_store.ensure_indexes()
    feedback_store = MongoFeedbackStore(
        mongo_client[mongo_settings.db_name][mongo_settings.interview_feedback_collection_name]
    )
    await feedback_store.ensure_indexes()
    completion_outbox = MongoCompletionOutbox(
        mongo_client[mongo_settings.db_name][mongo_settings.interview_completion_outbox_collection_name]
    )
    await completion_outbox.ensure_indexes()
    completed_publisher = AssessmentCompletedPublisher(
        amqp_url=settings.rabbitmq_settings.url,
        queue_name=settings.rabbitmq_settings.assessment_completed_queue_name,
    )
    completion_dispatcher = CompletionOutboxDispatcher(completion_outbox, completed_publisher)
    await completion_dispatcher.start()

    async with httpx.AsyncClient(timeout=user_management.timeout_seconds) as http_client:
        app.state.assessment_context_client = UserManagementAssessmentContextClient(
            client=http_client,
            base_url=user_management.url,
            service_token=user_management.internal_service_token,
        )
        app.state.interview_session_service = InterviewSessionService(
            journal=journal,
            lock=RedisSessionLock(redis_client),
            evaluator=PydanticAnswerEvaluator(parse_model_specs(settings.interview_evaluator_models)),
            interviewer=PydanticInterviewerAgent(parse_model_specs(settings.interview_interviewer_models)),
            cv_provider=MongoCandidateCvProvider(
                MongoRepository(
                    client=mongo_client,
                    db_name=mongo_settings.db_name,
                    collection_name=mongo_settings.cv_analysis_collection_name,
                )
            ),
            completed_publisher=completed_publisher,
            completion_outbox=completion_outbox,
            presence=RedisSessionPresence(redis_client),
        )
        app.state.assessment_report_service = AssessmentReportService(
            journal=journal,
            store=assessment_store,
            text_writer=PydanticAssessmentTextWriter(parse_model_specs(settings.interview_report_models)),
        )
        database = mongo_client[mongo_settings.db_name]
        app.state.attempt_erasure_service = AttemptErasureService(
            RedisSessionLock(redis_client),
            MongoAttemptDataEraser(
                events=database[mongo_settings.interview_events_collection_name],
                assessments=database[mongo_settings.interview_assessments_collection_name],
                reviews=database[mongo_settings.interview_assessment_reviews_collection_name],
                feedback=database[mongo_settings.interview_feedback_collection_name],
                cv_documents=database[mongo_settings.cv_analysis_collection_name],
            ),
        )
        app.state.candidate_feedback_service = CandidateFeedbackService(
            app.state.assessment_report_service,
            feedback_store,
            PydanticFeedbackWriter(parse_model_specs(settings.interview_feedback_models)),
        )
        app.state.spec_draft_service = SpecDraftService(
            PydanticSpecDrafter(parse_model_specs(settings.interview_spec_models))
        )
        try:
            yield
        finally:
            await completion_dispatcher.stop()
            await completed_publisher.close()
    await redis_client.aclose()
    mongo_client.close()
