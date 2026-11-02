import logging.config

from dependency_injector import providers
from dependency_injector.containers import DeclarativeContainer
from motor.motor_asyncio import AsyncIOMotorClient

from src.adapters.inbound.rabbitmq_consumer import RabbitMQConsumer
from src.adapters.outbound.mongo import MongoRepository
from src.adapters.outbound.pdf_loader import DoclingPDFLoader
from src.adapters.outbound.rabbitmq_producer import RabbitMQProducer
from src.adapters.outbound.s3 import S3Client
from src.agent.llm import LLMFactory
from src.agent.services.cv_analyzer import CVAnalyzer
from src.config import settings
from src.use_cases.cv_analyze_use_case import CVAnalyzeUseCase


class Container(DeclarativeContainer):
    yaml_config = providers.Configuration(yaml_files=["config.yaml"])

    logging_config = providers.Resource(logging.config.dictConfig, config=yaml_config.logger)

    app_logger = providers.Singleton(logging.getLogger, name="app")

    agent_logger = providers.Singleton(logging.getLogger, name="agent")

    llm = providers.Resource(LLMFactory.create_llm)
    cv_analyzer = providers.Singleton(CVAnalyzer, model=llm, logger=agent_logger)

    mongo_client = providers.Factory(AsyncIOMotorClient, settings.mongo_settings.url)
    mongo_cv_analysis_repository = providers.Factory(
        MongoRepository,
        client=mongo_client,
        db_name=settings.mongo_settings.db_name,
        collection_name=settings.mongo_settings.cv_analysis_collection_name,
    )

    s3_client = providers.Factory(
        S3Client,
        access_key=settings.s3_settings.access_key,
        secret_key=settings.s3_settings.secret_access_key,
        endpoint=settings.s3_settings.endpoint_url,
        bucket_name=settings.s3_settings.bucket_name,
        region_name=settings.s3_settings.region_name,
    )
    pdf_loader = providers.Factory(
        DoclingPDFLoader,
        do_ocr=settings.docling_settings.do_ocr,
        do_table_structure=settings.docling_settings.do_table_structure,
    )
    rabbitmq_producer_cv_results = providers.Factory(
        RabbitMQProducer,
        amqp_url=settings.rabbitmq_settings.url,
        queue_name=settings.rabbitmq_settings.cv_analysis_results_queue_name,
    )

    cv_analyze_use_case = providers.Factory(
        CVAnalyzeUseCase,
        s3_client=s3_client,
        cv_analyzer=cv_analyzer,
        pdf_loader=pdf_loader,
        mongo_repository=mongo_cv_analysis_repository,
        rabbitmq_producer=rabbitmq_producer_cv_results,
    )
    rabbitmq_consumer = providers.Factory(
        RabbitMQConsumer,
        amqp_url=settings.rabbitmq_settings.url,
        logger=app_logger,
        cv_analyze_use_case=cv_analyze_use_case,
    )
