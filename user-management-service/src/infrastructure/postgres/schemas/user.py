from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.user import User
from src.domain.value_objects.user_role import UserRole
from src.infrastructure.postgres.database import Base


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    first_name: Mapped[str]
    second_name: Mapped[str]
    username: Mapped[str] = mapped_column(unique=True)
    hashed_password: Mapped[str]
    phone_number: Mapped[str] = mapped_column(unique=True)
    email: Mapped[str] = mapped_column(unique=True)
    role: Mapped[UserRole]
    is_blocked: Mapped[bool] = mapped_column(default=False)
    is_email_verified: Mapped[bool] = mapped_column(default=False)
    subscription_tier: Mapped[str] = mapped_column(default="free")
    mfa_secret: Mapped[str | None] = mapped_column(default=None, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("TIMEZONE('utc', now())"),
    )
    modified_at: Mapped[datetime] = mapped_column(
        server_default=text("TIMEZONE('utc', now())"),
        onupdate=text("TIMEZONE('utc', now())"),
    )

    def to_entity(self) -> User:
        return User(
            id=self.id,
            first_name=self.first_name,
            second_name=self.second_name,
            username=self.username,
            hashed_password=self.hashed_password,
            phone_number=self.phone_number,
            email=self.email,
            role=self.role,
            is_blocked=self.is_blocked,
            created_at=self.created_at,
            modified_at=self.modified_at,
            is_email_verified=self.is_email_verified,
            subscription_tier=self.subscription_tier,
            mfa_secret=self.mfa_secret,
        )

    @classmethod
    def from_entity(cls, entity: User) -> "UserORM":
        return UserORM(
            id=entity.id,
            first_name=entity.first_name,
            second_name=entity.second_name,
            username=entity.username,
            hashed_password=entity.hashed_password,
            phone_number=entity.phone_number,
            email=entity.email,
            role=entity.role,
            is_blocked=entity.is_blocked,
            is_email_verified=entity.is_email_verified,
            subscription_tier=entity.subscription_tier,
            mfa_secret=entity.mfa_secret,
        )
