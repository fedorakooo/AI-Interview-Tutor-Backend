from uuid import UUID

from src.application.dtos.user import UserReadDTO
from src.application.mappers.user_mapper import UserMapper
from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.interfaces.database.uow import IUnitOfWork


class GetUserByIdUseCase:
    """UseCase to get a user by ID."""

    def __init__(
        self,
        uow: IUnitOfWork,
    ):
        self.uow = uow

    async def __call__(self, user_id: UUID) -> UserReadDTO:
        """Returns a user by its ID."""

        async with self.uow:
            user = await self.uow.user_repository.get_by_id(user_id)

        if user is None:
            raise NotFoundError(f"User with ID {user_id} not found")

        return UserMapper.from_entity_to_dto(user=user)
