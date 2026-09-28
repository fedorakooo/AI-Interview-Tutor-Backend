from abc import ABC, abstractmethod

from src.domain.interfaces.database.repositories.user_cv_upload_repository import IUserCVUploadRepository
from src.domain.interfaces.database.repositories.organization_repository import IOrganizationRepository
from src.domain.interfaces.database.repositories.vacancy_repository import IVacancyRepository
from src.domain.interfaces.database.repositories.user_repository import (
    IUserRepository,
)
from src.domain.interfaces.database.repositories.assessment_repository import IAssessmentRepository


class IUnitOfWork(ABC):
    @abstractmethod
    async def __aenter__(self) -> "IUnitOfWork":
        """Enter the async context manager."""
        pass

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the async context manager."""
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Commit the current transaction."""
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the current transaction."""
        pass

    @property
    @abstractmethod
    def user_repository(self) -> IUserRepository:
        """Provides access to the User repository."""
        pass

    @property
    @abstractmethod
    def user_cv_upload_repository(self) -> IUserCVUploadRepository:
        """Provides access to the CV upload repository."""
        pass

    @property
    @abstractmethod
    def organization_repository(self) -> IOrganizationRepository:
        """Provides access to organization and membership persistence."""
        pass

    @property
    @abstractmethod
    def vacancy_repository(self) -> IVacancyRepository:
        pass

    @property
    @abstractmethod
    def assessment_repository(self) -> IAssessmentRepository:
        pass
