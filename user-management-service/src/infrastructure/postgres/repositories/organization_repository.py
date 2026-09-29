from uuid import UUID

import sqlalchemy
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.organization import Organization, OrganizationMember
from src.domain.interfaces.database.repositories.organization_repository import IOrganizationRepository
from src.infrastructure.postgres.exceptions.database_errors import DatabaseError, DatabaseUniqueViolationError
from src.infrastructure.postgres.schemas.organization import OrganizationMemberORM, OrganizationORM


class OrganizationPostgresRepository(IOrganizationRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, organization: Organization) -> Organization:
        orm = OrganizationORM.from_entity(organization)
        self._session.add(orm)
        await self._flush(orm)
        return orm.to_entity()

    async def get_by_id_and_user_id(self, organization_id: UUID, user_id: UUID) -> Organization | None:
        query = (
            select(OrganizationORM)
            .join(OrganizationMemberORM, OrganizationMemberORM.organization_id == OrganizationORM.id)
            .where(
                OrganizationORM.id == organization_id,
                OrganizationMemberORM.user_id == user_id,
                OrganizationMemberORM.status == "active",
            )
        )
        result = await self._session.execute(query)
        orm = result.scalar_one_or_none()
        return orm.to_entity() if orm else None

    async def list_by_user_id(self, user_id: UUID) -> list[Organization]:
        query = (
            select(OrganizationORM)
            .join(OrganizationMemberORM, OrganizationMemberORM.organization_id == OrganizationORM.id)
            .where(OrganizationMemberORM.user_id == user_id, OrganizationMemberORM.status == "active")
            .order_by(OrganizationORM.created_at.desc())
        )
        result = await self._session.execute(query)
        return [organization.to_entity() for organization in result.scalars()]

    async def create_member(self, member: OrganizationMember) -> OrganizationMember:
        orm = OrganizationMemberORM.from_entity(member)
        self._session.add(orm)
        await self._flush(orm)
        return orm.to_entity()

    async def get_member(self, organization_id: UUID, user_id: UUID) -> OrganizationMember | None:
        result = await self._session.execute(
            select(OrganizationMemberORM).where(
                OrganizationMemberORM.organization_id == organization_id,
                OrganizationMemberORM.user_id == user_id,
            )
        )
        orm = result.scalar_one_or_none()
        return orm.to_entity() if orm else None

    async def list_members(self, organization_id: UUID) -> list[OrganizationMember]:
        result = await self._session.execute(
            select(OrganizationMemberORM)
            .where(OrganizationMemberORM.organization_id == organization_id)
            .order_by(OrganizationMemberORM.created_at)
        )
        return [member.to_entity() for member in result.scalars()]

    async def update_member(self, member: OrganizationMember) -> OrganizationMember:
        orm = OrganizationMemberORM.from_entity(member)
        updated = await self._session.merge(orm)
        await self._flush(updated)
        return updated.to_entity()

    async def _flush(self, orm: OrganizationORM | OrganizationMemberORM) -> None:
        try:
            await self._session.flush()
            await self._session.refresh(orm)
        except sqlalchemy.exc.IntegrityError as exc:
            message = str(exc.orig).lower()
            if "duplicate key" in message or "unique constraint" in message:
                raise DatabaseUniqueViolationError() from exc
            raise DatabaseError(message) from exc
