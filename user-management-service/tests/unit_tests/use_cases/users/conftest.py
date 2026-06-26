from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from src.application.dtos.user import UserReadDTO, UsersReadDTO, UserUpdateDTO
from src.domain.entities.user import User
from src.domain.interfaces.database.repositories.user_repository import IUserRepository
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.value_objects.user_filter import OrderField, UserFilter, UserSortField
from src.domain.value_objects.user_role import UserRole

from tests.conftest import faker


@pytest.fixture
def mock_user_repository():
    return AsyncMock(spec=IUserRepository)


@pytest.fixture
def mock_uow():
    return AsyncMock(spec=IUnitOfWork)


@pytest.fixture
def sample_now() -> datetime:
    return datetime.now()


@pytest.fixture
def sample_modified_at() -> datetime:
    return datetime.now() + timedelta(minutes=1)


@pytest.fixture
def sample_user_id() -> UUID:
    return uuid4()


@pytest.fixture
def sample_requesting_user_id() -> UUID:
    return uuid4()


@pytest.fixture
def sample_user(sample_user_id: UUID, sample_now: datetime) -> User:
    return User(
        id=sample_user_id,
        first_name=faker.first_name(),
        email=faker.email(),
        second_name=faker.last_name(),
        username=faker.user_name(),
        hashed_password=faker.password(),
        phone_number=faker.phone_number(),
        is_blocked=False,
        role=UserRole.USER,
        created_at=sample_now,
        modified_at=sample_now,
    )


@pytest.fixture
def sample_updated_user(sample_user: User, sample_modified_at: datetime) -> User:
    return User(
        id=sample_user.id,
        first_name=faker.first_name(),
        email=faker.email(),
        second_name=faker.last_name(),
        username=sample_user.username,
        hashed_password=sample_user.hashed_password,
        phone_number=faker.phone_number,
        is_blocked=sample_user.is_blocked,
        role=sample_user.role,
        created_at=sample_user.created_at,
        modified_at=sample_modified_at,
    )


@pytest.fixture
def sample_user_read_dto(sample_user: User) -> UserReadDTO:
    return UserReadDTO(
        id=sample_user.id,
        first_name=sample_user.first_name,
        email=sample_user.email,
        second_name=sample_user.second_name,
        username=sample_user.username,
        phone_number=sample_user.phone_number,
        role=sample_user.role,
        created_at=sample_user.created_at,
        modified_at=sample_user.modified_at,
    )


@pytest.fixture
def sample_user_update_dto(sample_updated_user: User, sample_now: datetime) -> UserUpdateDTO:
    return UserUpdateDTO(
        first_name=sample_updated_user.first_name,
        second_name=sample_updated_user.second_name,
        phone_number=sample_updated_user.phone_number,
        email=sample_updated_user.email,
    )


@pytest.fixture
def sample_updated_user_read_dto(sample_updated_user: User) -> UserReadDTO:
    return UserReadDTO(
        id=sample_updated_user.id,
        first_name=sample_updated_user.first_name,
        email=sample_updated_user.email,
        second_name=sample_updated_user.second_name,
        username=sample_updated_user.username,
        phone_number=sample_updated_user.phone_number,
        role=sample_updated_user.role,
        created_at=sample_updated_user.created_at,
        modified_at=sample_updated_user.modified_at,
    )


@pytest.fixture
def sample_user_after_leaving_group(sample_user: User, sample_modified_at: datetime) -> User:
    return User(
        id=sample_user.id,
        first_name=sample_user.first_name,
        email=sample_user.email,
        second_name=sample_user.second_name,
        username=sample_user.username,
        phone_number=sample_user.phone_number,
        role=sample_user.role,
        hashed_password=sample_user.hashed_password,
        is_blocked=sample_user.is_blocked,
        created_at=sample_user.created_at,
        modified_at=sample_modified_at,
    )


@pytest.fixture
def sample_user_list(sample_user: User) -> tuple[list[User], int]:
    return [sample_user], 1


@pytest.fixture
def sample_users_read_dto(sample_user_read_dto: UserReadDTO) -> UsersReadDTO:
    return UsersReadDTO(users=[sample_user_read_dto], total=1)


@pytest.fixture
def sample_default_user_filter() -> UserFilter:
    return UserFilter(
        page=1,
        limit=30,
        sort_by=UserSortField.SECOND_NAME,
        order_by=OrderField.DESC,
    )
