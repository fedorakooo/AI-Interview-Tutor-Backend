from abc import ABC, abstractmethod

from src.domain.interfaces.database.repositories.user_repository import (
    IUserRepository,
)


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
