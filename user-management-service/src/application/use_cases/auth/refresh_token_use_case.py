from datetime import datetime

from jwt_handler.dtos import TokenInfoDTO
from jwt_handler.exceptions import InvalidTokenError
from jwt_handler.interfaces import (
    IAccessTokenGenerator,
    IRefreshTokenGenerator,
    ITokenHandler,
)
from jwt_handler.value_objects import AuthType, TokenType

from src.domain.exceptions.user_errors import UserBlockedError
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.interfaces.redis.redis_client import IRedisClient


class RefreshTokenUseCase:
    """UseCase to refresh access and refresh tokens."""

    def __init__(
        self,
        uow: IUnitOfWork,
        redis_client: IRedisClient,
        token_handler: ITokenHandler,
        access_token_generator: IAccessTokenGenerator,
        refresh_token_generator: IRefreshTokenGenerator,
    ):
        self.uow = uow
        self.redis_client = redis_client
        self.token_handler = token_handler
        self.access_token_generator = access_token_generator
        self.refresh_token_generator = refresh_token_generator

    async def __call__(self, refresh_token: str) -> TokenInfoDTO:
        """Refreshes access and refresh tokens using a valid refresh token."""

        payload = self.token_handler.decode_jwt(refresh_token)

        if payload.get("type") != TokenType.REFRESH:
            raise InvalidTokenError()

        username = payload.get("username")
        if username is None:
            raise InvalidTokenError()

        async with self.uow:
            user = await self.uow.user_repository.get_by_username(username)

        if user is None:
            raise InvalidTokenError()
        if user.is_blocked:
            raise UserBlockedError(username)

        if await self.redis_client.exists(f"refresh-key:{refresh_token}"):
            raise InvalidTokenError()

        access_token = self.access_token_generator.generate_access_token(
            user_id=str(user.id),
            username=username,
            user_role=user.role,
            is_blocked=user.is_blocked,
        )
        new_refresh_token = self.refresh_token_generator.generate_refresh_token(
            user_id=str(user.id),
            username=username,
        )

        expiration_time = payload.get("exp")

        if expiration_time is None:
            raise InvalidTokenError()

        current_time = datetime.now().timestamp()
        ttl_seconds = int(expiration_time - current_time)

        await self.redis_client.setex(
            key=f"refresh-key:{refresh_token}",
            value=refresh_token,
            time=ttl_seconds,
        )

        return TokenInfoDTO(
            access_token=access_token,
            refresh_token=new_refresh_token,
            auth_type=AuthType.BEARER,
        )
