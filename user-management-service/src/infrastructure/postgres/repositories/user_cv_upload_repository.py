from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.user_cv_upload import UserCVUpload
from src.domain.interfaces.database.repositories.user_cv_upload_repository import IUserCVUploadRepository
from src.infrastructure.postgres.schemas.user_cv_upload import UserCVUploadORM


class UserCVUploadPostgresRepository(IUserCVUploadRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, upload: UserCVUpload) -> UserCVUpload:
        orm = UserCVUploadORM.from_entity(upload)
        self._session.add(orm)
        await self._session.flush()
        await self._session.refresh(orm)
        return orm.to_entity()

    async def update(self, upload: UserCVUpload) -> UserCVUpload:
        orm = await self._session.get(UserCVUploadORM, upload.id)
        if orm is None:
            raise ValueError(f"CV upload {upload.id} not found")

        orm.status = upload.status.value
        orm.error_code = upload.error_code
        orm.error_message = upload.error_message
        orm.mongo_document_id = upload.mongo_document_id
        await self._session.flush()
        await self._session.refresh(orm)
        return orm.to_entity()

    async def get_latest_by_user_id(self, user_id: UUID) -> UserCVUpload | None:
        stmt = (
            select(UserCVUploadORM)
            .where(UserCVUploadORM.user_id == user_id)
            .order_by(UserCVUploadORM.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return orm.to_entity() if orm else None

    async def get_by_correlation_id(self, correlation_id: UUID) -> UserCVUpload | None:
        stmt = select(UserCVUploadORM).where(UserCVUploadORM.correlation_id == correlation_id)
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return orm.to_entity() if orm else None

    async def get_by_user_and_correlation_id(self, user_id: UUID, correlation_id: UUID) -> UserCVUpload | None:
        stmt = select(UserCVUploadORM).where(
            UserCVUploadORM.user_id == user_id,
            UserCVUploadORM.correlation_id == correlation_id,
        )
        result = await self._session.execute(stmt)
        orm = result.scalar_one_or_none()
        return orm.to_entity() if orm else None
