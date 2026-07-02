from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import Dependency, Factory
from motor.motor_asyncio import AsyncIOMotorClient

from src.adapters.outbound.mongo import MongoRepository
from src.adapters.outbound.pdf_loader import DoclingPDFLoader
from src.adapters.outbound.rabbitmq_producer import RabbitMQProducer
from src.adapters.outbound.s3 import S3Client
from src.config import settings


class OutboundAdaptersContainer(DeclarativeContainer):
    logger = Dependency()

    mongo_client = Factory(
        AsyncIOMotorClient,
        settings.mongo_settings.url,
    )

    mongo_cv_analysis_repository = Factory(
        MongoRepository,
        client=mongo_client,
        db_name=settings.mongo_settings.db_name,
        collection_name=settings.mongo_settings.cv_analysis_collection_name,
    )

    s3_client = Factory(
        S3Client,
        access_key=settings.s3_settings.access_key,
        secret_key=settings.s3_settings.secret_access_key,
        endpoint=settings.s3_settings.endpoint_url,
        bucket_name=settings.s3_settings.bucket_name,
        region_name=settings.s3_settings.region_name,
    )

    pdf_loader = Factory(
        DoclingPDFLoader,
        do_ocr=settings.docling_settings.do_ocr,
        do_table_structure=settings.docling_settings.do_table_structure,
    )

    rabbitmq_producer_cv_results = Factory(
        RabbitMQProducer,
        amqp_url=settings.rabbitmq_settings.url,
        queue_name=settings.rabbitmq_settings.cv_analysis_results_queue_name,
    )
