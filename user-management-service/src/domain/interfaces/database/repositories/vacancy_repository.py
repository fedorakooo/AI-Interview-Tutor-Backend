from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.entities.vacancy import AssessmentTemplate, Vacancy


class IVacancyRepository(ABC):
    @abstractmethod
    async def create(self, vacancy: Vacancy, template: AssessmentTemplate) -> Vacancy:
        pass

    @abstractmethod
    async def get_by_id_and_organization_id(self, vacancy_id: UUID, organization_id: UUID) -> Vacancy | None:
        pass

    @abstractmethod
    async def list_by_organization_id(self, organization_id: UUID) -> list[Vacancy]:
        pass

    @abstractmethod
    async def get_template(self, vacancy_id: UUID, version: int) -> AssessmentTemplate | None:
        pass

    @abstractmethod
    async def update(self, vacancy: Vacancy) -> Vacancy:
        pass

    @abstractmethod
    async def update_template(self, template: AssessmentTemplate) -> AssessmentTemplate:
        pass
