from abc import ABC, abstractmethod
from uuid import UUID

from src.infrastructure.postgres.schemas.notification_preference import NotificationPreferenceORM


class INotificationPreferenceRepository(ABC):
    """Persistent notification settings for a platform user."""

    @abstractmethod
    async def get_by_user_id(self, user_id: UUID) -> NotificationPreferenceORM | None: ...

    @abstractmethod
    async def upsert(self, preference: NotificationPreferenceORM) -> NotificationPreferenceORM: ...
