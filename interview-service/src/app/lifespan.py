from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

from src.agent.workflow import create_interview_workflow
from src.api.v1.managers.interview_manager import InterviewConnectionManager
from src.config import settings
from src.infrastructure.mongo import MongoRepository
from src.infrastructure.postgres.checkpointer import create_checkpointer
from src.infrastructure.rabbitmq.interview_completed_producer import InterviewCompletedProducer
from src.infrastructure.postgres.pool import create_postgres_pool
from src.infrastructure.redis.client import create_redis_client
from src.infrastructure.redis.session_registry import RedisSessionRegistry
from src.logger import app_logger
from src.repositories.interview_session_repository import InterviewSessionRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    instance_id = InterviewConnectionManager.resolve_instance_id(settings.instance_settings.id) or str(uuid4())
    postgres_pool = await create_postgres_pool()
    await postgres_pool.open()
    checkpointer = await create_checkpointer(postgres_pool)
    workflow = create_interview_workflow(checkpointer)
    redis_client = create_redis_client()
    session_registry = RedisSessionRegistry(redis_client, instance_id=instance_id)
    mongo_client = AsyncIOMotorClient(settings.mongo_settings.url)
    session_repository = InterviewSessionRepository(
        MongoRepository(
            client=mongo_client,
            db_name=settings.mongo_settings.db_name,
            collection_name=settings.mongo_settings.interview_sessions_collection_name,
        )
    )
    interview_completed_producer = InterviewCompletedProducer(
        amqp_url=settings.rabbitmq_settings.url,
        queue_name=settings.rabbitmq_settings.interview_completed_queue_name,
    )
    interview_manager = InterviewConnectionManager(
        interview_workflow=workflow,
        session_registry=session_registry,
        session_repository=session_repository,
        instance_id=instance_id,
        interview_completed_producer=interview_completed_producer,
    )

    app.state.postgres_pool = postgres_pool
    app.state.redis_client = redis_client
    app.state.mongo_client = mongo_client
    app.state.interview_manager = interview_manager
    app.state.instance_id = instance_id

    app_logger.info("Interview service started on instance %s", instance_id)
    yield

    await interview_manager.shutdown()
    await redis_client.aclose()
    mongo_client.close()
    await postgres_pool.close()
    app_logger.info("Interview service stopped")
