from functools import lru_cache

from motor.motor_asyncio import AsyncIOMotorClient

from src.config import settings
from src.domain.interfaces.mongo import IMongoRepository
from src.infrastructure.mongo import MongoRepository
from src.repositories.interview_session_repository import InterviewSessionRepository


@lru_cache
def get_mongo_client() -> AsyncIOMotorClient:
    return AsyncIOMotorClient(settings.mongo_settings.url)


def get_cv_analysis_repository() -> IMongoRepository:
    return MongoRepository(
        client=get_mongo_client(),
        db_name=settings.mongo_settings.db_name,
        collection_name=settings.mongo_settings.cv_analysis_collection_name,
    )


def get_interview_session_repository() -> InterviewSessionRepository:
    return InterviewSessionRepository(
        MongoRepository(
            client=get_mongo_client(),
            db_name=settings.mongo_settings.db_name,
            collection_name=settings.mongo_settings.interview_sessions_collection_name,
        )
    )
