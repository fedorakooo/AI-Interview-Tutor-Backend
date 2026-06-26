import uuid

from src.application.dtos.user import UserCreateDTO, UserReadDTO
from src.application.mappers.user_mapper import UserMapper
from src.domain.interfaces.auth.password_handler import IPasswordHandler
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.value_objects.user_role import UserRole


class UserRegistrationUseCase:
    """UseCase to register a new user."""

    def __init__(
        self,
        uow: IUnitOfWork,
        password_handler: IPasswordHandler,
    ):
        self.uow = uow
        self.password_handler = password_handler

    async def __call__(self, user_create: UserCreateDTO) -> UserReadDTO:
        """Creates a new user by hashing the password. Returns the created user"""

        user_id = uuid.uuid4()

        hashed_password = self.password_handler.hash_password(user_create.password)

        user = UserMapper.from_create_dto_to_entity(
            user_create=user_create,
            user_id=user_id,
            hashed_password=hashed_password,
            user_role=UserRole.USER,
            is_blocked=False,
        )

        async with self.uow as uow:
            created_user = await uow.user_repository.create(user)

        return UserMapper.from_entity_to_dto(created_user)
