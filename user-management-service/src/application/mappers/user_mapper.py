from datetime import datetime
from uuid import UUID

from src.application.dtos.user import UserCreateDTO, UserReadDTO, UserUpdateDTO
from src.domain.entities.user import User
from src.domain.value_objects.user_role import UserRole


class UserMapper:
    """Mapper for converting between User DTOs and Entities."""

    @staticmethod
    def from_entity_to_dto(user: User) -> UserReadDTO:
        """Converts User entity to UserReadDTO."""
        return UserReadDTO(
            id=user.id,
            first_name=user.first_name,
            second_name=user.second_name,
            username=user.username,
            phone_number=user.phone_number,
            email=user.email,
            role=user.role,
            is_blocked=user.is_blocked,
            created_at=user.created_at,
            modified_at=user.modified_at,
        )

    @staticmethod
    def from_create_dto_to_entity(
        user_create: UserCreateDTO,
        user_id: UUID,
        hashed_password: str,
        user_role: UserRole,
        is_blocked: bool,
    ) -> User:
        """Converts UserCreateDTO to User entity."""
        now = datetime.now()
        return User(
            id=user_id,
            first_name=user_create.first_name,
            second_name=user_create.second_name,
            username=user_create.username,
            hashed_password=hashed_password,
            phone_number=user_create.phone_number,
            email=user_create.email,
            role=user_role,
            is_blocked=is_blocked,
            created_at=now,
            modified_at=now,
        )

    @staticmethod
    def from_update_dto_to_entity(
        user_update_dto: UserUpdateDTO,
        current_user: User,
    ) -> User:
        """Converts UserUpdateDTO to User entity."""
        now = datetime.now()
        return User(
            id=current_user.id,
            first_name=(user_update_dto.first_name if user_update_dto.first_name else current_user.first_name),
            second_name=(user_update_dto.second_name if user_update_dto.second_name else current_user.second_name),
            username=current_user.username,
            hashed_password=current_user.hashed_password,
            phone_number=(user_update_dto.phone_number if user_update_dto.phone_number else current_user.phone_number),
            email=(user_update_dto.email if user_update_dto.email else current_user.email),
            role=current_user.role,
            is_blocked=(
                user_update_dto.is_blocked if user_update_dto.is_blocked is not None else current_user.is_blocked
            ),
            created_at=current_user.created_at,
            modified_at=now,
        )
