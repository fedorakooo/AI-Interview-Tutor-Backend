import logging
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from jwt_handler.interfaces import IAccessTokenGenerator, IRefreshTokenGenerator
from src.application.use_cases.auth.user_login_use_case import LoginUserUseCase
from src.domain.entities.user import User
from src.domain.exceptions.login_errors import InvalidPasswordError, InvalidUsernameError
from src.domain.interfaces.auth.password_handler import IPasswordHandler
from src.domain.interfaces.database.repositories.user_repository import IUserRepository
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.value_objects.user_role import UserRole
from tests.conftest import faker


@pytest.fixture
def mock_uow() -> AsyncMock:
    uow = AsyncMock(spec=IUnitOfWork)
    uow.user_repository = AsyncMock(spec=IUserRepository)
    return uow


@pytest.fixture
def mock_password_handler() -> MagicMock:
    return MagicMock(spec=IPasswordHandler)


@pytest.fixture
def mock_access_token_generator() -> MagicMock:
    return MagicMock(spec=IAccessTokenGenerator)


@pytest.fixture
def mock_refresh_token_generator() -> MagicMock:
    return MagicMock(spec=IRefreshTokenGenerator)


@pytest.fixture
def use_case(
    mock_uow: AsyncMock,
    mock_access_token_generator: MagicMock,
    mock_refresh_token_generator: MagicMock,
    mock_password_handler: MagicMock,
) -> LoginUserUseCase:
    return LoginUserUseCase(
        uow=mock_uow,
        access_token_generator=mock_access_token_generator,
        refresh_token_generator=mock_refresh_token_generator,
        password_handler=mock_password_handler,
    )


@pytest.fixture
def sample_user() -> User:
    now = datetime.now()
    return User(
        id=uuid4(),
        first_name=faker.first_name(),
        second_name=faker.last_name(),
        username=faker.user_name(),
        phone_number=faker.phone_number(),
        email=faker.email(),
        hashed_password=faker.sha256(),
        role=UserRole.USER,
        is_blocked=False,
        created_at=now,
        modified_at=now,
    )


class TestLoginUserUseCase:
    @pytest.mark.asyncio
    async def test_login_with_invalid_password_raises_and_does_not_leak_password(
        self,
        use_case: LoginUserUseCase,
        mock_uow: AsyncMock,
        mock_password_handler: MagicMock,
        mock_access_token_generator: MagicMock,
        sample_user: User,
        caplog: pytest.LogCaptureFixture,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        password = "s3cr3t-Pa55word!"
        mock_uow.user_repository.get_by_username.return_value = sample_user
        mock_password_handler.validate_password.return_value = False

        with caplog.at_level(logging.DEBUG), pytest.raises(InvalidPasswordError):
            await use_case(sample_user.username, password)

        mock_password_handler.validate_password.assert_called_once_with(
            password=password,
            hashed_password=sample_user.hashed_password,
        )
        mock_access_token_generator.generate_access_token.assert_not_called()
        captured = capsys.readouterr()
        assert password not in captured.out
        assert password not in captured.err
        assert password not in caplog.text
        assert str(sample_user.id) in caplog.text

    @pytest.mark.asyncio
    async def test_login_with_unknown_username_raises(
        self,
        use_case: LoginUserUseCase,
        mock_uow: AsyncMock,
        mock_password_handler: MagicMock,
    ) -> None:
        mock_uow.user_repository.get_by_username.return_value = None

        with pytest.raises(InvalidUsernameError):
            await use_case("unknown-user", "any-password")

        mock_password_handler.validate_password.assert_not_called()
