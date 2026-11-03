from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from src.app.container import build_container
from src.config import settings
from src.infrastructure.redis.client import create_redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo_settings = settings.mongo_settings
    mongo_client = AsyncIOMotorClient(mongo_settings.url)
    redis_client = create_redis_client()

    async with httpx.AsyncClient(timeout=settings.user_management_settings.timeout_seconds) as http_client:
        container = build_container(mongo_client, redis_client, http_client)
        for repository in container.indexed_repositories:
            await repository.ensure_indexes()
        await container.completion_dispatcher.start()

        app.state.container = container
        app.state.mongo_client = mongo_client
        app.state.redis_client = redis_client
        try:
            yield
        finally:
            await container.completion_dispatcher.stop()
            await container.completed_publisher.close()
    await redis_client.aclose()
    mongo_client.close()
