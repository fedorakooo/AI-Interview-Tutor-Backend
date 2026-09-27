from uuid import UUID, uuid4

from shared_models.assessment.contracts import AssessmentTemplateSnapshot, TemplateStatus, VacancyStatus

from src.domain.entities.vacancy import AssessmentTemplate, Vacancy
from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.interfaces.database.uow import IUnitOfWork


class CreateVacancyUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def __call__(
        self,
        organization_id: UUID,
        actor_user_id: UUID,
        title: str,
        job_description: str,
        seniority: str,
        language: str,
        snapshot: AssessmentTemplateSnapshot,
    ) -> Vacancy:
        vacancy = Vacancy(
            id=uuid4(),
            organization_id=organization_id,
            title=title.strip(),
            job_description=job_description.strip(),
            seniority=seniority.strip(),
            language=language.strip(),
            status=VacancyStatus.DRAFT,
            created_by=actor_user_id,
        )
        template = AssessmentTemplate(
            id=uuid4(),
            vacancy_id=vacancy.id,
            version=1,
            snapshot=snapshot,
            status=TemplateStatus.DRAFT,
            created_by=actor_user_id,
        )
        async with self._uow:
            return await self._uow.vacancy_repository.create(vacancy, template)


class ActivateVacancyUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def __call__(self, vacancy_id: UUID, organization_id: UUID) -> Vacancy:
        async with self._uow:
            vacancy = await self._uow.vacancy_repository.get_by_id_and_organization_id(vacancy_id, organization_id)
            if vacancy is None:
                raise NotFoundError("Vacancy not found")
            template = await self._uow.vacancy_repository.get_template(vacancy_id, 1)
            if template is None:
                raise NotFoundError("Assessment template not found")
            template.status = TemplateStatus.ACTIVE
            await self._uow.vacancy_repository.update_template(template)
            vacancy.status = VacancyStatus.ACTIVE
            vacancy.active_template_version = template.version
            return await self._uow.vacancy_repository.update(vacancy)
