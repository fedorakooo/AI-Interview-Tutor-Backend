from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from shared_models.assessment.contracts import AssessmentTemplateSnapshot, TemplateStatus, VacancyStatus


@dataclass
class Vacancy:
    id: UUID
    organization_id: UUID
    title: str
    job_description: str
    seniority: str
    language: str
    status: VacancyStatus
    created_by: UUID
    active_template_version: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class AssessmentTemplate:
    id: UUID
    vacancy_id: UUID
    version: int
    snapshot: AssessmentTemplateSnapshot
    status: TemplateStatus
    created_by: UUID
    created_at: datetime | None = None
