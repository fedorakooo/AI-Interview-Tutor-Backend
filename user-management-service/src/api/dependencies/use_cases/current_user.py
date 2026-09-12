from typing import Annotated

from fastapi import Depends

from src.api.dependencies.database import get_unit_of_work
from src.api.dependencies.rabbitmq import get_user_deleted_producer
from src.api.dependencies.redis import get_redis_client
from src.api.dependencies.s3 import get_s3_client
from src.application.use_cases.current_user.delete_current_user_use_case import DeleteCurrentUserUseCase
from src.application.use_cases.current_user.get_current_user_use_case import GetCurrentUserUseCase
from src.application.use_cases.current_user.update_current_user_use_case import UpdateCurrentUserUseCase
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.interfaces.rabbitmq.rabbitmq_producer import IRabbitMQProducer
from src.domain.interfaces.redis.redis_client import IRedisClient
from src.domain.interfaces.storage.s3_client import IS3Client


def get_current_user_use_case(uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)]) -> GetCurrentUserUseCase:
    return GetCurrentUserUseCase(
        uow=uow,
    )


def get_update_current_user_use_case(
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
) -> UpdateCurrentUserUseCase:
    return UpdateCurrentUserUseCase(
        uow=uow,
    )


def get_delete_current_user_use_case(
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    redis_client: Annotated[IRedisClient, Depends(get_redis_client)],
    s3_client: Annotated[IS3Client, Depends(get_s3_client)],
    data_cleanup_producer: Annotated[IRabbitMQProducer, Depends(get_user_deleted_producer)],
) -> DeleteCurrentUserUseCase:
    return DeleteCurrentUserUseCase(
        uow=uow,
        redis_client=redis_client,
        s3_client=s3_client,
        data_cleanup_producer=data_cleanup_producer,
    )
