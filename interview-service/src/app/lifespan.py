from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from src.application.interview.session_service import InterviewSessionService
from src.config import settings
from src.infrastructure.ai.evaluator import PydanticAnswerEvaluator
from src.infrastructure.ai.interviewer import PydanticInterviewerAgent
from src.infrastructure.ai.models import parse_model_specs
from src.infrastructure.mongo import MongoRepository
from src.infrastructure.mongo_candidate_cv_provider import MongoCandidateCvProvider
from src.infrastructure.mongo_event_journal import MongoEventJournal
from src.infrastructure.rabbitmq.assessment_completed_publisher import AssessmentCompletedPublisher
from src.infrastructure.redis.client import create_redis_client
from src.infrastructure.redis.session_lock import RedisSessionLock
from src.infrastructure.user_management.assessment_context_client import UserManagementAssessmentContextClient
from src.legacy.runtime import legacy_runtime


@asynccontextmanager
async def lifespan(app: FastAPI):
    user_management = settings.user_management_settings
    mongo_settings = settings.mongo_settings
    mongo_client = AsyncIOMotorClient(mongo_settings.url)
    journal = MongoEventJournal(mongo_client[mongo_settings.db_name][mongo_settings.interview_events_collection_name])
    await journal.ensure_indexes()

    async with httpx.AsyncClient(timeout=user_management.timeout_seconds) as http_client:
        app.state.assessment_context_client = UserManagementAssessmentContextClient(
            client=http_client,
            base_url=user_management.url,
            service_token=user_management.internal_service_token,
        )
        app.state.interview_session_service = InterviewSessionService(
            journal=journal,
            lock=RedisSessionLock(create_redis_client()),
            evaluator=PydanticAnswerEvaluator(parse_model_specs(settings.interview_evaluator_models)),
            interviewer=PydanticInterviewerAgent(parse_model_specs(settings.interview_interviewer_models)),
            cv_provider=MongoCandidateCvProvider(
                MongoRepository(
                    client=mongo_client,
                    db_name=mongo_settings.db_name,
                    collection_name=mongo_settings.cv_analysis_collection_name,
                )
            ),
            completed_publisher=AssessmentCompletedPublisher(
                amqp_url=settings.rabbitmq_settings.url,
                queue_name=settings.rabbitmq_settings.assessment_completed_queue_name,
            ),
        )
        async with legacy_runtime(app):
            yield
    mongo_client.close()
