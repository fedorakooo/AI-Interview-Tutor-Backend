from src.application.dtos.user import UsersReadDTO
from src.application.mappers.user_mapper import UserMapper
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.value_objects.user_filter import UserFilter


class GetUsersUseCase:
    """UseCase to get users by filter."""

    def __init__(self, uow: IUnitOfWork):
        self.uow = uow

    async def __call__(self, user_filter: UserFilter) -> UsersReadDTO:
        """Returns a list of users according to the filter."""

        async with self.uow as uow:
            users, total = await uow.user_repository.get_users(user_filter)

        users_dto = [UserMapper.from_entity_to_dto(user=user) for user in users]

        return UsersReadDTO(
            users=users_dto,
            total=total,
        )
