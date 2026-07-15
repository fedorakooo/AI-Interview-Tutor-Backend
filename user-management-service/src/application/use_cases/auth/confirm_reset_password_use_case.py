from uuid import UUID

from jwt_handler.exceptions import ExpiredSignatureError, InvalidTokenError
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
        except (InvalidTokenError, ExpiredSignatureError) as exc:
            raise NotFoundError("Invalid or expired reset token") from exc

        if payload.get("type") != PASSWORD_RESET_TOKEN_TYPE:
            raise NotFoundError("Invalid or expired reset token")

        user_id = payload.get("id")
        if user_id is None:
            raise NotFoundError("Invalid or expired reset token")

        async with self.uow as uow:
            user = await uow.user_repository.get_by_id(UUID(user_id))
            if user is None:
                raise NotFoundError("Invalid or expired reset token")

            user.hashed_password = self.password_handler.hash_password(new_password)
            await uow.user_repository.update(user)
