from datetime import datetime

from jwt_handler.exceptions import InvalidTokenError
from jwt_handler.interfaces import ITokenHandler
from jwt_handler.value_objects import TokenType

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
        if expiration_time is None:
            raise InvalidTokenError()

        ttl_seconds = int(expiration_time - datetime.now().timestamp())
        if ttl_seconds <= 0:
            return

        await self.redis_client.setex(
            key=f"refresh-key:{refresh_token}",
            value=refresh_token,
            time=ttl_seconds,
        )
