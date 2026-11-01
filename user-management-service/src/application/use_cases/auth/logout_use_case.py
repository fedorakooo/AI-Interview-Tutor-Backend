from datetime import UTC, datetime
from math import ceil

from jwt_handler.exceptions import InvalidTokenError
from jwt_handler.interfaces import ITokenHandler
from jwt_handler.value_objects import TokenType

from src.application.use_cases.auth.refresh_token_use_case import refresh_token_key
from src.domain.interfaces.redis.redis_client import IRedisClient


class LogoutUseCase:
    """Blacklist the presented refresh token so it cannot be reused."""

    def __init__(self, redis_client: IRedisClient, token_handler: ITokenHandler):
        self.redis_client = redis_client
        self.token_handler = token_handler

    async def __call__(self, refresh_token: str) -> None:
        payload = self.token_handler.decode_jwt(refresh_token)
        if payload.get("type") != TokenType.REFRESH:
            raise InvalidTokenError()

        expiration_time = payload.get("exp")
        if not isinstance(expiration_time, int | float):
            raise InvalidTokenError()

        ttl_seconds = ceil(expiration_time - datetime.now(UTC).timestamp())
        if ttl_seconds <= 0:
            return

        await self.redis_client.setex(
            key=refresh_token_key(refresh_token),
            value="1",
            time=ttl_seconds,
        )
