from uuid import UUID

import sqlalchemy
from sqlalchemy import asc, delete, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.user import User
from src.domain.interfaces.database.repositories.user_repository import IUserRepository
from src.domain.value_objects.user_filter import OrderField, UserFilter
from src.infrastructure.postgres.exceptions.database_errors import (
    DatabaseError,
    DatabaseUniqueViolationError,
)
from src.infrastructure.postgres.schemas.user import UserORM


class UserPostgresRepository(IUserRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        query = select(UserORM).where(UserORM.id == user_id)
        result = await self._session.execute(query)
        user_orm = result.scalar_one_or_none()
        return user_orm.to_entity() if user_orm else None

    async def get_by_username(self, username: str) -> User | None:
        query = select(UserORM).where(UserORM.username == username)
        result = await self._session.execute(query)
        user_orm = result.scalar_one_or_none()
        return user_orm.to_entity() if user_orm else None

    async def get_by_email(self, email: str) -> User | None:
        query = select(UserORM).where(UserORM.email == email)
        result = await self._session.execute(query)
        user_orm = result.scalar_one_or_none()
        return user_orm.to_entity() if user_orm else None

    async def get_users(self, user_filter: UserFilter) -> tuple[list[User], int]:
        sort_column = getattr(UserORM, user_filter.sort_by)
        sort_expr = asc(sort_column) if user_filter.order_by == OrderField.ASC else desc(sort_column)

        base_query = select(UserORM).order_by(sort_expr)
        if user_filter.name:
            base_query = base_query.where(
                or_(
                    UserORM.name == user_filter.name,
                    UserORM.username == user_filter.name,
                )
            )

        count_query = select(func.count()).select_from(base_query.subquery())
        count_result = await self._session.execute(count_query)
        total_count = count_result.scalar_one()

        query = (
            base_query.order_by(sort_expr).offset((user_filter.page - 1) * user_filter.limit).limit(user_filter.limit)
        )

        result = await self._session.execute(query)
        users_orm = result.scalars().all()

        return [user_orm.to_entity() for user_orm in users_orm], total_count

    async def create(self, user: User) -> User:
        user_orm = UserORM.from_entity(user)
        self._session.add(user_orm)
        try:
            await self._session.flush()
            await self._session.refresh(user_orm)
        except sqlalchemy.exc.IntegrityError as exc:
            self._handle_integrity_error(exc)
        return user_orm.to_entity()

    async def update(self, user: User) -> User:
        user_orm = UserORM.from_entity(user)
        updated_user = await self._session.merge(user_orm)
        try:
            await self._session.flush()
            await self._session.refresh(updated_user)
        except sqlalchemy.exc.IntegrityError as exc:
            self._handle_integrity_error(exc)
        return updated_user.to_entity()

    async def delete(self, user_id: UUID) -> bool:
        query = delete(UserORM).where(UserORM.id == user_id)
        result = await self._session.execute(query)
        await self._session.flush()
        return result.rowcount == 1

    def _handle_integrity_error(self, exc: sqlalchemy.exc.IntegrityError) -> None:
        """Handles SQLAlchemy IntegrityError exceptions raised during database operations."""
        message = str(exc.orig).lower()
        if "duplicate key" in message:
            raise DatabaseUniqueViolationError() from exc
        raise DatabaseError(message) from exc
