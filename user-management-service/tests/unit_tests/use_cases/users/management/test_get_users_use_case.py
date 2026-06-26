from unittest.mock import AsyncMock

import pytest
from src.application.dtos.user import UsersReadDTO
from src.application.use_cases.user_management.get_users_use_case import GetUsersUseCase
from src.domain.entities.user import User
from src.domain.value_objects.user_filter import UserFilter


class TestGetUsersUseCase:
    @pytest.mark.asyncio
    async def test_get_users_by_admin_success(
        self,
        mock_uow: AsyncMock,
        mock_user_repository: AsyncMock,
        sample_user_list: tuple[list[User], int],
        sample_users_read_dto: UsersReadDTO,
        sample_default_user_filter: UserFilter,
    ) -> None:
        mock_uow.__aenter__.return_value = mock_uow
        mock_uow.user_repository = mock_user_repository
        mock_user_repository.get_users = AsyncMock()
        mock_user_repository.get_users.return_value = sample_user_list
        use_case = GetUsersUseCase(mock_uow)

        result = await use_case(user_filter=sample_default_user_filter)

        assert result == sample_users_read_dto
        mock_user_repository.get_users.assert_awaited_once_with(sample_default_user_filter)
