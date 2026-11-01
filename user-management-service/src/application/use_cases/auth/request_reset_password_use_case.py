import json
import logging
from datetime import UTC, datetime
from typing import cast

from jwt_handler.interfaces import ITokenHandler
from jwt_handler.value_objects import RefreshTokenPayload

from src.config import settings
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.interfaces.rabbitmq.rabbitmq_producer import IRabbitMQProducer

PASSWORD_RESET_TOKEN_TYPE = "PASSWORD_RESET"
PASSWORD_RESET_EXPIRE_MINUTES = 30
logger = logging.getLogger(__name__)


class RequestResetPasswordUseCase:
    """Issues a password-reset token and publishes a notification job."""

    def __init__(
        self,
        uow: IUnitOfWork,
        token_handler: ITokenHandler,
        reset_password_producer: IRabbitMQProducer,
    ):
        self.uow = uow
        self.token_handler = token_handler
        self.reset_password_producer = reset_password_producer

    async def __call__(self, email: str) -> str | None:
        async with self.uow:
            user = await self.uow.user_repository.get_by_email(email)

        if user is None or user.is_blocked:
            return None

        payload = cast(
            RefreshTokenPayload,
            {
                "id": str(user.id),
                "username": user.email,
                "type": PASSWORD_RESET_TOKEN_TYPE,
                "auth_version": user.auth_version,
            },
        )
        reset_token = self.token_handler.encode_jwt(payload, expire_minutes=PASSWORD_RESET_EXPIRE_MINUTES)

        reset_url = settings.frontend_settings.reset_password_url
        message = {
            "user_id": str(user.id),
            "email": user.email,
            "subject": "Password Reset Request",
            "body": f"Click the link to reset your password: {reset_url}?token={reset_token}",
            "published_at": datetime.now(UTC).isoformat(),
        }
        try:
            await self.reset_password_producer.send_message(json.dumps(message))
        except Exception:
            # Preserve the same public response for existing and absent accounts
            # even when the notification dependency is unavailable.
            logger.error("Failed to enqueue password reset notification")
            return None

        return reset_token
