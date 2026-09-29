from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.interfaces.database.repositories.notification_preference_repository import INotificationPreferenceRepository
from src.infrastructure.postgres.schemas.notification_preference import NotificationPreferenceORM


class NotificationPreferencePostgresRepository(INotificationPreferenceRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_user_id(self, user_id: UUID) -> NotificationPreferenceORM | None:
        return await self._session.get(NotificationPreferenceORM, user_id)

    async def upsert(self, preference: NotificationPreferenceORM) -> NotificationPreferenceORM:
        persisted = await self._session.merge(preference)
        await self._session.flush()
        await self._session.refresh(persisted)
        return persisted
