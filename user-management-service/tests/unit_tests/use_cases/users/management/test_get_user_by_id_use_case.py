from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from src.application.dtos.user import UserReadDTO
from src.application.use_cases.user_management.get_user_by_id_use_case import GetUserByIdUseCase
from src.domain.entities.user import User
from src.domain.exceptions.not_found_error import NotFoundError


class TestGetUserByIdUseCase:
    @pytest.mark.asyncio
    async def test_get_user_by_id_admin_success(
        self,
        mock_uow: AsyncMock,
        mock_user_repository: AsyncMock,
        sample_user_id: UUID,
        sample_user,
        sample_user_read_dto,
    ) -> None:
        mock_user_repository.get_by_id.return_value = sample_user
        mock_uow.user_repository = mock_user_repository
        use_case = GetUserByIdUseCase(mock_uow)

        result = await use_case(sample_user_id)

        assert result == sample_user_read_dto

        mock_uow.user_repository.get_by_id.assert_awaited_once_with(sample_user_id)

    @pytest.mark.asyncio
    async def test_get_user_by_id_moderator_success(
        self,
        mock_uow: AsyncMock,
        mock_user_repository: AsyncMock,
        sample_user: User,
        sample_user_read_dto: UserReadDTO,
        sample_user_id: UUID,
    ) -> None:
        mock_user_repository.get_by_id.return_value = sample_user
        mock_uow.user_repository = mock_user_repository
        use_case = GetUserByIdUseCase(mock_uow)

        result = await use_case(sample_user_id)

        assert result == sample_user_read_dto

        mock_user_repository.get_by_id.assert_awaited_once_with(sample_user_id)

    @pytest.mark.asyncio
    async def test_get_user_by_id_moderator_forbidden(
        self,
        mock_uow: AsyncMock,
        mock_user_repository: AsyncMock,
        sample_user: User,
        sample_user_id: UUID,
    ) -> None:
        mock_user_repository.get_by_id.return_value = sample_user
        mock_uow.user_repository = mock_user_repository
        use_case = GetUserByIdUseCase(mock_uow)

        await use_case(sample_user_id)

        mock_uow.user_repository.get_by_id.assert_awaited_once_with(sample_user_id)

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(
        self,
        mock_uow: AsyncMock,
        mock_user_repository: AsyncMock,
        sample_user_id: UUID,
    ) -> None:
        mock_user_repository.get_by_id.return_value = None
        mock_uow.user_repository = mock_user_repository
        use_case = GetUserByIdUseCase(mock_uow)

        with pytest.raises(NotFoundError):
            await use_case(sample_user_id)

        mock_uow.user_repository.get_by_id.assert_awaited_once_with(sample_user_id)
