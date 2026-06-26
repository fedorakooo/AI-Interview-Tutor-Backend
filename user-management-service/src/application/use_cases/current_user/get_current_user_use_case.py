from uuid import UUID

from jwt_handler.exceptions import InvalidTokenError
from jwt_handler.value_objects import AccessTokenPayload

from src.application.dtos.user import UserReadDTO
from src.application.mappers.user_mapper import UserMapper
from src.domain.interfaces.database.uow import IUnitOfWork


class GetCurrentUserUseCase:
    """UseCase to get the current user."""

    def __init__(self, uow: IUnitOfWork):
        self.uow = uow

    async def __call__(self, access_token: AccessTokenPayload) -> UserReadDTO:
        """Returns the current user."""

        async with self.uow:
            requesting_user = await self.uow.user_repository.get_by_id(UUID(access_token["id"]))

        if not requesting_user:
            raise InvalidTokenError()

        return UserMapper.from_entity_to_dto(
            user=requesting_user,
        )
