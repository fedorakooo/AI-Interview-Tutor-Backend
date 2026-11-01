from uuid import UUID

from jwt_handler.exceptions import InvalidTokenError
from jwt_handler.value_objects import AccessTokenPayload

from src.domain.exceptions.login_errors import InvalidPasswordError
from src.domain.exceptions.user_errors import UserBlockedError
from src.domain.interfaces.auth.password_handler import IPasswordHandler
from src.domain.interfaces.database.uow import IUnitOfWork


class ChangePasswordUseCase:
    def __init__(self, uow: IUnitOfWork, password_handler: IPasswordHandler):
        self.uow = uow
        self.password_handler = password_handler

    async def __call__(self, payload: AccessTokenPayload, current_password: str, new_password: str) -> None:
        async with self.uow:
            user = await self.uow.user_repository.get_by_id(UUID(payload["id"]), for_update=True)
            if user is None or payload.get("auth_version", 0) != user.auth_version:
                raise InvalidTokenError()
            if user.is_blocked:
                raise UserBlockedError(user.username)
            if not self.password_handler.validate_password(current_password, user.hashed_password):
                raise InvalidPasswordError()
            user.hashed_password = self.password_handler.hash_password(new_password)
            user.auth_version += 1
            await self.uow.user_repository.update(user)
