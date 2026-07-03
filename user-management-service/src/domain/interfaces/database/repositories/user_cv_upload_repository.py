from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.user_cv_upload import UserCVUpload


class IUserCVUploadRepository(ABC):
    @abstractmethod
    async def create(self, upload: UserCVUpload) -> UserCVUpload:
        pass

    @abstractmethod
    async def update(self, upload: UserCVUpload) -> UserCVUpload:
        pass

    @abstractmethod
    async def get_latest_by_user_id(self, user_id: UUID) -> UserCVUpload | None:
        pass

    @abstractmethod
    async def get_by_correlation_id(self, correlation_id: UUID) -> UserCVUpload | None:
        pass

    @abstractmethod
    async def get_by_user_and_correlation_id(self, user_id: UUID, correlation_id: UUID) -> UserCVUpload | None:
        pass
