from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.vacancy import AssessmentTemplate, Vacancy
from src.domain.interfaces.database.repositories.vacancy_repository import IVacancyRepository
from src.infrastructure.postgres.schemas.vacancy import AssessmentTemplateORM, VacancyORM


class VacancyPostgresRepository(IVacancyRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, vacancy: Vacancy, template: AssessmentTemplate) -> Vacancy:
        orm = VacancyORM.from_entity(vacancy)
        self._session.add_all([orm, AssessmentTemplateORM.from_entity(template)])
        await self._session.flush()
        await self._session.refresh(orm)
        return orm.to_entity()

    async def get_by_id_and_organization_id(self, vacancy_id: UUID, organization_id: UUID) -> Vacancy | None:
        result = await self._session.execute(select(VacancyORM).where(VacancyORM.id == vacancy_id, VacancyORM.organization_id == organization_id))
        value = result.scalar_one_or_none()
        return value.to_entity() if value else None

    async def list_by_organization_id(self, organization_id: UUID) -> list[Vacancy]:
        result = await self._session.execute(select(VacancyORM).where(VacancyORM.organization_id == organization_id).order_by(VacancyORM.created_at.desc()))
        return [value.to_entity() for value in result.scalars()]

    async def get_template(self, vacancy_id: UUID, version: int) -> AssessmentTemplate | None:
        result = await self._session.execute(select(AssessmentTemplateORM).where(AssessmentTemplateORM.vacancy_id == vacancy_id, AssessmentTemplateORM.version == version))
        value = result.scalar_one_or_none()
        return value.to_entity() if value else None

    async def update(self, vacancy: Vacancy) -> Vacancy:
        updated = await self._session.merge(VacancyORM.from_entity(vacancy))
        await self._session.flush()
        await self._session.refresh(updated)
        return updated.to_entity()

    async def update_template(self, template: AssessmentTemplate) -> AssessmentTemplate:
        updated = await self._session.merge(AssessmentTemplateORM.from_entity(template))
        await self._session.flush()
        await self._session.refresh(updated)
        return updated.to_entity()
