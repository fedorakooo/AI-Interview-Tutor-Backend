from uuid import UUID

from jwt_handler.exceptions import InvalidTokenError
from jwt_handler.value_objects import AccessTokenPayload

from src.application.dtos.user import UserReadDTO, UserUpdateDTO
from src.application.mappers.user_mapper import UserMapper
from src.domain.interfaces.database.uow import IUnitOfWork


class UpdateCurrentUserUseCase:
    """UseCase to update the current user."""

    def __init__(self, uow: IUnitOfWork):
        self.uow = uow

    async def __call__(
        self,
        access_token: AccessTokenPayload,
        user_update_dto: UserUpdateDTO,
    ) -> UserReadDTO:
        """Updates the current user and returns the updated user."""

        async with self.uow:
            current_user = await self.uow.user_repository.get_by_id(UUID(access_token["id"]))

            if current_user is None:
                raise InvalidTokenError()

            user_update = UserMapper.from_update_dto_to_entity(
                user_update_dto=user_update_dto,
                current_user=current_user,
            )
            updated_user = await self.uow.user_repository.update(user_update)

        return UserMapper.from_entity_to_dto(
            user=updated_user,
        )
