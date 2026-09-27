from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.organization import Organization, OrganizationMember


class IOrganizationRepository(ABC):
    @abstractmethod
    async def create(self, organization: Organization) -> Organization:
        pass

    @abstractmethod
    async def get_by_id_and_user_id(self, organization_id: UUID, user_id: UUID) -> Organization | None:
        """Look up an organization only if the given user is a member."""

    @abstractmethod
    async def list_by_user_id(self, user_id: UUID) -> list[Organization]:
        pass

    @abstractmethod
    async def create_member(self, member: OrganizationMember) -> OrganizationMember:
        pass

    @abstractmethod
    async def get_member(self, organization_id: UUID, user_id: UUID) -> OrganizationMember | None:
        pass

    @abstractmethod
    async def list_members(self, organization_id: UUID) -> list[OrganizationMember]:
        pass
