from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from src.application.dtos.user import UserReadDTO, UserUpdateDTO
from src.application.use_cases.user_management.update_user_use_case import UpdateUserUseCase
from src.domain.entities.user import User
from src.domain.exceptions.not_found_error import NotFoundError


class TestUpdateUserUseCase:
    @pytest.mark.asyncio
    async def test_update_user_success(
        self,
        mock_uow: AsyncMock,
        mock_user_repository: AsyncMock,
        sample_user_id: UUID,
        sample_user: User,
        sample_updated_user: User,
        sample_user_update_dto: UserUpdateDTO,
        sample_updated_user_read_dto: UserReadDTO,
    ) -> None:
        mock_user_repository.get_by_id.return_value = sample_user
        mock_user_repository.update.return_value = sample_updated_user
        mock_uow.user_repository = mock_user_repository

        use_case = UpdateUserUseCase(mock_uow)

        result = await use_case(sample_user_id, sample_user_update_dto)

        assert result == sample_updated_user_read_dto

        mock_user_repository.get_by_id.assert_awaited_once_with(sample_user_id)
        mock_user_repository.update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_user_not_found(
        self,
        mock_uow: AsyncMock,
        mock_user_repository: AsyncMock,
        sample_user_id: UUID,
        sample_user_update_dto: UserUpdateDTO,
    ) -> None:
        mock_user_repository.get_by_id.return_value = None
        mock_uow.user_repository = mock_user_repository
        use_case = UpdateUserUseCase(mock_uow)

        with pytest.raises(NotFoundError):
            await use_case(sample_user_id, sample_user_update_dto)

        mock_user_repository.get_by_id.assert_awaited_once_with(sample_user_id)
        mock_user_repository.update.assert_not_awaited()
