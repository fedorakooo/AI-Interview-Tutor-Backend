from typing import Annotated

from fastapi import Depends

from src.api.dependencies.database import get_unit_of_work
from src.api.dependencies.rabbitmq import get_cv_analyzer_producer
from src.api.dependencies.s3 import get_s3_client
from src.application.use_cases.cv.get_cv_status_use_case import GetCVStatusUseCase
from src.application.use_cases.cv.upload_cv_use_case import UploadCVUseCase
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.interfaces.rabbitmq.rabbitmq_producer import IRabbitMQProducer
from src.domain.interfaces.storage.s3_client import IS3Client


def get_upload_cv_use_case(
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    s3_client: Annotated[IS3Client, Depends(get_s3_client)],
    cv_analyzer_producer: Annotated[IRabbitMQProducer, Depends(get_cv_analyzer_producer)],
) -> UploadCVUseCase:
    return UploadCVUseCase(
        uow=uow,
        s3_client=s3_client,
        cv_analyzer_producer=cv_analyzer_producer,
    )


def get_cv_status_use_case(
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
) -> GetCVStatusUseCase:
    return GetCVStatusUseCase(uow=uow)
