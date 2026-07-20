from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.value_objects.user_role import UserRole


@dataclass(frozen=True, slots=True)
class UserCreateDTO:
    first_name: str
    second_name: str
    username: str
    phone_number: str
    password: str
    email: str


@dataclass(frozen=True, slots=True)
class UserUpdateDTO:
    first_name: str | None
    second_name: str | None
    phone_number: str | None
    email: str | None
    is_blocked: bool | None = None


@dataclass(frozen=True, slots=True)
class UserReadDTO:
    id: UUID
    first_name: str
    second_name: str
    username: str
    phone_number: str
    email: str
    role: UserRole
    is_blocked: bool
    created_at: datetime
    modified_at: datetime


@dataclass(frozen=True, slots=True)
class UsersReadDTO:
    users: list[UserReadDTO]
    total: int
