from uuid import UUID, uuid4

from src.domain.entities.organization import Organization, OrganizationMember
from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.exceptions.organization_errors import OrganizationAccessError
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.value_objects.organization_role import OrganizationRole


class CreateOrganizationUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def __call__(self, owner_user_id: UUID, name: str) -> Organization:
        organization = Organization(id=uuid4(), name=name.strip(), owner_user_id=owner_user_id, plan="free", retention_days=365)
        async with self._uow:
            created = await self._uow.organization_repository.create(organization)
            await self._uow.organization_repository.create_member(
                OrganizationMember(created.id, owner_user_id, OrganizationRole.ADMIN, invited_by=owner_user_id)
            )
        return created


class ListMyOrganizationsUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def __call__(self, user_id: UUID) -> list[Organization]:
        async with self._uow:
            return await self._uow.organization_repository.list_by_user_id(user_id)


class AddOrganizationMemberUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def __call__(self, organization_id: UUID, actor_user_id: UUID, member_email: str, role: OrganizationRole) -> OrganizationMember:
        async with self._uow:
            actor = await self._uow.organization_repository.get_member(organization_id, actor_user_id)
            if actor is None:
                raise NotFoundError("Organization not found")
            if actor.status != "active" or actor.role != OrganizationRole.ADMIN:
                raise OrganizationAccessError()
            user = await self._uow.user_repository.get_by_email(member_email.lower())
            if user is None:
                raise NotFoundError("User not found")
            return await self._uow.organization_repository.create_member(
                OrganizationMember(organization_id, user.id, role, invited_by=actor_user_id)
            )
