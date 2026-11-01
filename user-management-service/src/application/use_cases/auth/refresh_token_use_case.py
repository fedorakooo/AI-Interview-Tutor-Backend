from datetime import UTC, datetime
from hashlib import sha256
from math import ceil
from uuid import UUID

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


def refresh_token_key(token: str) -> str:
    return f"refresh-key:{sha256(token.encode()).hexdigest()}"


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

        try:
            user_id = UUID(payload["id"])
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            raise InvalidTokenError() from exc

        async with self.uow:
            user = await self.uow.user_repository.get_by_id(user_id)

        if user is None:
            raise InvalidTokenError()
        if user.is_blocked:
            raise UserBlockedError(user.username)

        version = payload.get("auth_version", 0)
        if type(version) is not int or version != user.auth_version:
            raise InvalidTokenError()

        # Honor revocations written before refresh keys were hashed.
        if await self.redis_client.exists(f"refresh-key:{refresh_token}"):
            raise InvalidTokenError()

        expiration_time = payload.get("exp")
        if not isinstance(expiration_time, int | float):
            raise InvalidTokenError()
        ttl_seconds = ceil(expiration_time - datetime.now(UTC).timestamp())
        if ttl_seconds <= 0:
            raise InvalidTokenError()
        if not await self.redis_client.set_if_absent(key=refresh_token_key(refresh_token), time=ttl_seconds, value="1"):
            raise InvalidTokenError()

        access_token = self.access_token_generator.generate_access_token(
            user_id=str(user.id),
            username=user.username,
            user_role=user.role,
            is_blocked=user.is_blocked,
            auth_version=user.auth_version,
        )
        new_refresh_token = self.refresh_token_generator.generate_refresh_token(
            user_id=str(user.id),
            username=user.username,
            auth_version=user.auth_version,
        )

        return TokenInfoDTO(
            access_token=access_token,
            refresh_token=new_refresh_token,
            auth_type=AuthType.BEARER,
        )
