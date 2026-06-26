from typing import Annotated

from fastapi import Depends
from jwt_handler.interfaces import (
    IAccessTokenGenerator,
    IRefreshTokenGenerator,
    ITokenHandler,
)

from src.api.dependencies.auth import (
    get_access_token_generator,
    get_password_handler,
    get_refresh_token_generator,
    get_token_handler,
)
from src.api.dependencies.database import get_unit_of_work
from src.api.dependencies.rabbitmq import get_reset_password_producer
from src.api.dependencies.redis import get_redis_client
from src.application.use_cases.auth.confirm_reset_password_use_case import ConfirmResetPasswordUseCase
from src.application.use_cases.auth.refresh_token_use_case import RefreshTokenUseCase
from src.application.use_cases.auth.request_reset_password_use_case import RequestResetPasswordUseCase
from src.application.use_cases.auth.user_login_use_case import LoginUserUseCase
from src.application.use_cases.auth.user_registration_use_case import (
    UserRegistrationUseCase,
)
from src.domain.interfaces.auth.password_handler import IPasswordHandler
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.interfaces.rabbitmq.rabbitmq_producer import IRabbitMQProducer
from src.domain.interfaces.redis.redis_client import IRedisClient


def get_user_registration_use_case(
    password_handler: Annotated[IPasswordHandler, Depends(get_password_handler)],
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
) -> UserRegistrationUseCase:
    return UserRegistrationUseCase(
        password_handler=password_handler,
        uow=uow,
    )


def get_login_user_use_case(
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    access_token_generator: Annotated[IAccessTokenGenerator, Depends(get_access_token_generator)],
    refresh_token_generator: Annotated[IRefreshTokenGenerator, Depends(get_refresh_token_generator)],
    password_handler: Annotated[IPasswordHandler, Depends(get_password_handler)],
) -> LoginUserUseCase:
    return LoginUserUseCase(
        access_token_generator=access_token_generator,
        refresh_token_generator=refresh_token_generator,
        password_handler=password_handler,
        uow=uow,
    )


def get_refresh_token_use_case(
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    redis_client: Annotated[IRedisClient, Depends(get_redis_client)],
    token_handler: Annotated[ITokenHandler, Depends(get_token_handler)],
    access_token_generator: Annotated[IAccessTokenGenerator, Depends(get_access_token_generator)],
    refresh_token_generator: Annotated[IRefreshTokenGenerator, Depends(get_refresh_token_generator)],
) -> RefreshTokenUseCase:
    return RefreshTokenUseCase(
        access_token_generator=access_token_generator,
        refresh_token_generator=refresh_token_generator,
        token_handler=token_handler,
        uow=uow,
        redis_client=redis_client,
    )


def get_request_reset_password_use_case(
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    token_handler: Annotated[ITokenHandler, Depends(get_token_handler)],
    reset_password_producer: Annotated[IRabbitMQProducer, Depends(get_reset_password_producer)],
) -> RequestResetPasswordUseCase:
    return RequestResetPasswordUseCase(
        uow=uow,
        token_handler=token_handler,
        reset_password_producer=reset_password_producer,
    )


def get_confirm_reset_password_use_case(
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    token_handler: Annotated[ITokenHandler, Depends(get_token_handler)],
    password_handler: Annotated[IPasswordHandler, Depends(get_password_handler)],
) -> ConfirmResetPasswordUseCase:
    return ConfirmResetPasswordUseCase(
        uow=uow,
        token_handler=token_handler,
        password_handler=password_handler,
    )
