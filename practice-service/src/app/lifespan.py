from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from src.app.container import build_container
from src.config import settings
from src.infrastructure.mongo.client import MongoClientFactory
from src.infrastructure.rabbitmq.consumers import PracticeConsumers
from src.logger import app_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo_client = MongoClientFactory.create(settings.mongo_settings.url)
    container, generate_plan_use_case, handle_interview_use_case, plan_repo, attempt_repo, profile_repo = (
        build_container(mongo_client)
    )

    await plan_repo.ensure_indexes()
    await attempt_repo.ensure_indexes()
    await profile_repo.ensure_indexes()

    consumers = PracticeConsumers(generate_plan_use_case, handle_interview_use_case)
    await consumers.start()

    app.state.container = container
    app.state.mongo_client = mongo_client
    app.state.consumers = consumers

    app_logger.info("Practice service started")
    yield

    await consumers.stop()
    mongo_client.close()
    app_logger.info("Practice service stopped")


def get_container(request: Request):
    return request.app.state.container
