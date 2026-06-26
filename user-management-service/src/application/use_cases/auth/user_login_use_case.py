from jwt_handler.dtos import TokenInfoDTO
from jwt_handler.interfaces import (
    IAccessTokenGenerator,
    IRefreshTokenGenerator,
)
from jwt_handler.value_objects import AuthType

from src.domain.exceptions.login_errors import (
    InvalidPasswordError,
    InvalidUsernameError,
)
from src.domain.exceptions.user_errors import UserBlockedError
from src.domain.interfaces.auth.password_handler import IPasswordHandler
from src.domain.interfaces.database.uow import IUnitOfWork


class LoginUserUseCase:
    """UseCase to handle user authentication."""

    def __init__(
        self,
        uow: IUnitOfWork,
        access_token_generator: IAccessTokenGenerator,
        refresh_token_generator: IRefreshTokenGenerator,
        password_handler: IPasswordHandler,
    ):
        self.uow = uow
        self.access_token_generator = access_token_generator
        self.refresh_token_generator = refresh_token_generator
        self.password_handler = password_handler

    async def __call__(self, username: str, password: str) -> TokenInfoDTO:
        """Checks user credentials and returns access token"""

        async with self.uow:
            user = await self.uow.user_repository.get_by_username(username)
        if user is None:
            raise InvalidUsernameError(username)

        is_password_correct = self.password_handler.validate_password(
            password=password,
            hashed_password=user.hashed_password,
        )

        if not is_password_correct:
            print(username, password)
            raise InvalidPasswordError()

        if user.is_blocked:
            raise UserBlockedError(username)

        access_token = self.access_token_generator.generate_access_token(
            user_id=str(user.id),
            username=username,
            user_role=user.role,
            is_blocked=user.is_blocked,
        )
        refresh_token = self.refresh_token_generator.generate_refresh_token(
            user_id=str(user.id),
            username=username,
        )
        return TokenInfoDTO(
            access_token=access_token,
            refresh_token=refresh_token,
            auth_type=AuthType.BEARER,
        )
