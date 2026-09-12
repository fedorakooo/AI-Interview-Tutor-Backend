import json
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from jwt_handler.interfaces import ITokenHandler
from jwt_handler.value_objects import RefreshTokenPayload

from src.config import settings
from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.interfaces.rabbitmq.rabbitmq_producer import IRabbitMQProducer

EMAIL_VERIFY_TOKEN_TYPE = "EMAIL_VERIFY"
EMAIL_VERIFY_EXPIRE_MINUTES = 60 * 24


class RequestEmailVerificationUseCase:
    """Issues an email-verification token and publishes a notification job."""

    def __init__(
        self,
        uow: IUnitOfWork,
        token_handler: ITokenHandler,
        email_verify_producer: IRabbitMQProducer,
    ):
        self.uow = uow
        self.token_handler = token_handler
        self.email_verify_producer = email_verify_producer

    async def __call__(self, user_id: UUID) -> None:
        async with self.uow:
            user = await self.uow.user_repository.get_by_id(user_id)

        if user is None:
            raise NotFoundError("User not found")
        if user.is_email_verified:
            return

        payload = cast(
            RefreshTokenPayload,
            {
                "id": str(user.id),
                "username": user.email,
                "type": EMAIL_VERIFY_TOKEN_TYPE,
            },
        )
        verify_token = self.token_handler.encode_jwt(payload, expire_minutes=EMAIL_VERIFY_EXPIRE_MINUTES)
        verify_url = settings.frontend_settings.verify_email_url
        message = {
            "user_id": str(user.id),
            "email": user.email,
            "email_type": "email_verify",
            "subject": "Verify your email",
            "body": f"Click the link to verify your email: {verify_url}?token={verify_token}",
            "published_at": datetime.now(UTC).isoformat(),
        }
        await self.email_verify_producer.send_message(json.dumps(message))


class ConfirmEmailVerificationUseCase:
    """Marks the user email as verified when the token is valid."""

    def __init__(self, uow: IUnitOfWork, token_handler: ITokenHandler):
        self.uow = uow
        self.token_handler = token_handler

    async def __call__(self, token: str) -> None:
        from jwt_handler.exceptions import InvalidTokenError, TokenExpiredError

        from src.domain.exceptions.not_found_error import NotFoundError as DomainNotFound

        try:
            payload = self.token_handler.decode_jwt(token)
        except (InvalidTokenError, TokenExpiredError) as exc:
            raise DomainNotFound("Invalid or expired verification token") from exc

        if payload.get("type") != EMAIL_VERIFY_TOKEN_TYPE:
            raise DomainNotFound("Invalid or expired verification token")

        user_id = payload.get("id")
        if not user_id:
            raise DomainNotFound("Invalid or expired verification token")

        async with self.uow:
            user = await self.uow.user_repository.get_by_id(UUID(str(user_id)))
            if user is None:
                raise DomainNotFound("Invalid or expired verification token")
            if user.is_email_verified:
                return
            user.is_email_verified = True
            await self.uow.user_repository.update(user)
