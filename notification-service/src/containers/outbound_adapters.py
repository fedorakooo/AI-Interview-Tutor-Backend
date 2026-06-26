import boto3
from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import Dependency, Factory, Singleton
from pymongo import MongoClient

from src.adapters.outbound.mongo_repository import MongoRepository
from src.adapters.outbound.ses_client import SESClient
from src.config import settings


class OutboundAdaptersContainer(DeclarativeContainer):
    logger = Dependency()

    mongo_client = Singleton(
        MongoClient,
        settings.mongo_settings.url,
    )

    messages_mongo_repository = Factory(
        MongoRepository,
        client=mongo_client,
        db_name=settings.mongo_settings.db_name,
        collection_name=settings.mongo_settings.messages_collection_name,
    )

    aws_ses_client = Singleton(
        lambda: boto3.client(
            "ses",
            aws_access_key_id=settings.ses_settings.aws_access_key,
            aws_secret_access_key=settings.ses_settings.aws_secret_access_key,
            region_name=settings.ses_settings.aws_region,
        )
    )

    ses_client = Factory(
        SESClient,
        client=aws_ses_client,
        sender_email=settings.ses_settings.sender_email,
        logger=logger,
    )
