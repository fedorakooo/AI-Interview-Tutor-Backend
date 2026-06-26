from uuid import UUID

from src.application.dtos.user import UserReadDTO, UserUpdateDTO
from src.application.mappers.user_mapper import UserMapper
from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.interfaces.database.uow import IUnitOfWork


class UpdateUserUseCase:
    """UseCase to update a user by its ID."""

    def __init__(self, uow: IUnitOfWork):
        self.uow = uow

    async def __call__(
        self,
        user_id: UUID,
        user_update_dto: UserUpdateDTO,
    ) -> UserReadDTO:
        """Updates a user and returns the updated user."""

        async with self.uow:
            user = await self.uow.user_repository.get_by_id(user_id)

            if user is None:
                raise NotFoundError(f"User with ID {user_id} not found")

            user_update = UserMapper.from_update_dto_to_entity(
                user_update_dto=user_update_dto,
                current_user=user,
            )

            updated_user = await self.uow.user_repository.update(user_update)

        return UserMapper.from_entity_to_dto(user=updated_user)
