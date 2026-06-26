from uuid import UUID

from jwt_handler.value_objects import AccessTokenPayload

from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.interfaces.database.uow import IUnitOfWork


class DeleteCurrentUserUseCase:
    """UseCase to delete the current user."""

    def __init__(self, uow: IUnitOfWork):
        self.uow = uow

    async def __call__(self, access_token: AccessTokenPayload) -> None:
        """Deletes the current user."""

        async with self.uow:
            result = await self.uow.user_repository.delete(UUID(access_token["id"]))

        if not result:
            raise NotFoundError(f"User with ID {access_token["id"]} not found")
