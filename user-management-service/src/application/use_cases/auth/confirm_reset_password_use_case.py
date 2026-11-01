from uuid import UUID

from jwt_handler.exceptions import TokenError
from jwt_handler.interfaces import ITokenHandler

from src.application.use_cases.auth.request_reset_password_use_case import PASSWORD_RESET_TOKEN_TYPE
from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.interfaces.auth.password_handler import IPasswordHandler
from src.domain.interfaces.database.uow import IUnitOfWork


class ConfirmResetPasswordUseCase:
    """Resets a user password using a valid password-reset token."""

    def __init__(
        self,
        uow: IUnitOfWork,
        token_handler: ITokenHandler,
        password_handler: IPasswordHandler,
    ):
        self.uow = uow
        self.token_handler = token_handler
        self.password_handler = password_handler

    async def __call__(self, token: str, new_password: str) -> None:
        try:
            payload = self.token_handler.decode_jwt(token)
        except TokenError as exc:
            raise NotFoundError("Invalid or expired reset token") from exc

        if payload.get("type") != PASSWORD_RESET_TOKEN_TYPE:
            raise NotFoundError("Invalid or expired reset token")

        try:
            user_id = UUID(payload["id"])
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            raise NotFoundError("Invalid or expired reset token") from exc

        async with self.uow as uow:
            user = await uow.user_repository.get_by_id(user_id, for_update=True)
            if (
                user is None
                or user.is_blocked
                or payload.get("username") != user.email
                or payload.get("auth_version") != user.auth_version
            ):
                raise NotFoundError("Invalid or expired reset token")

            user.hashed_password = self.password_handler.hash_password(new_password)
            user.auth_version += 1
            await uow.user_repository.update(user)
