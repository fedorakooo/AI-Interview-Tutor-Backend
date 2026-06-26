from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, SecretStr, field_validator

from src.api.v1.models.validators.user_validators import (
    NameValidator,
    PasswordValidator,
    PhoneValidator,
    UsernameValidator,
)
from src.application.dtos.user import (
    UserCreateDTO,
    UserReadDTO,
    UsersReadDTO,
    UserUpdateDTO,
)
from src.domain.value_objects.user_role import UserRole


class UserCreateRequest(BaseModel):
    first_name: str
    second_name: str
    username: str
    phone_number: str
    password: SecretStr
    email: EmailStr

    @field_validator("first_name", "second_name")
    def validate_names(cls, v) -> str:
        return NameValidator.validate(v)

    @field_validator("username")
    def validate_username(cls, v) -> str:
        return UsernameValidator.validate(v)

    @field_validator("phone_number")
    def validate_phone(cls, v) -> str:
        return PhoneValidator.validate(v)

    @field_validator("password")
    def validate_password(cls, v) -> SecretStr:
        return PasswordValidator.validate(v)

    def to_dto(self) -> UserCreateDTO:
        return UserCreateDTO(
            first_name=self.first_name,
            second_name=self.second_name,
            username=self.username,
            password=self.password.get_secret_value(),
            phone_number=self.phone_number,
            email=str(self.email),
        )


class UserResponse(BaseModel):
    id: UUID
    first_name: str
    second_name: str
    username: str
    phone_number: str
    email: EmailStr
    role: UserRole
    created_at: datetime
    modified_at: datetime

    @classmethod
    def from_dto(cls, user: UserReadDTO) -> "UserResponse":
        return UserResponse(
            id=user.id,
            first_name=user.first_name,
            second_name=user.second_name,
            username=user.username,
            email=user.email,
            phone_number=user.phone_number,
            created_at=user.created_at,
            modified_at=user.modified_at,
            role=user.role,
        )


class UserUpdateRequest(BaseModel):
    first_name: str | None = None
    second_name: str | None = None
    phone_number: str | None = None
    email: EmailStr | None = None

    @field_validator("first_name", "second_name")
    def validate_names(cls, v) -> str | None:
        if v is not None:
            return NameValidator.validate(v)
        return v

    @field_validator("phone_number")
    def validate_phone(cls, v) -> str | None:
        if v is not None:
            return PhoneValidator.validate(v)
        return v

    def to_dto(self) -> UserUpdateDTO:
        return UserUpdateDTO(
            first_name=self.first_name,
            second_name=self.second_name,
            phone_number=self.phone_number,
            email=self.email,
        )


class UsersResponse(BaseModel):
    users: list[UserResponse]
    total: int

    @classmethod
    def from_dto(cls, users_dto: UsersReadDTO) -> "UsersResponse":
        return UsersResponse(
            users=[UserResponse.from_dto(user) for user in users_dto.users],
            total=users_dto.total,
        )
