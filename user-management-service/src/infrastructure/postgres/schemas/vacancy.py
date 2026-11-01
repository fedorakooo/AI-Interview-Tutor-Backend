from datetime import datetime
from uuid import UUID

from shared_models.assessment.contracts import AssessmentTemplateSnapshot, TemplateStatus, VacancyStatus
from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.vacancy import AssessmentTemplate, Vacancy
from src.infrastructure.postgres.database import Base


class VacancyORM(Base):
    __tablename__ = "vacancies"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    job_description: Mapped[str] = mapped_column(String)
    seniority: Mapped[str] = mapped_column(String(64))
    language: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default=VacancyStatus.DRAFT.value)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    active_template_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("TIMEZONE('utc', now())"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("TIMEZONE('utc', now())"), onupdate=text("TIMEZONE('utc', now())"))

    def to_entity(self) -> Vacancy:
        return Vacancy(
            id=self.id,
            organization_id=self.organization_id,
            title=self.title,
            job_description=self.job_description,
            seniority=self.seniority,
            language=self.language,
            status=VacancyStatus(self.status),
            created_by=self.created_by,
            active_template_version=self.active_template_version,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, value: Vacancy) -> "VacancyORM":
        return cls(
            id=value.id,
            organization_id=value.organization_id,
            title=value.title,
            job_description=value.job_description,
            seniority=value.seniority,
            language=value.language,
            status=value.status.value,
            created_by=value.created_by,
            active_template_version=value.active_template_version,
        )


class AssessmentTemplateORM(Base):
    __tablename__ = "assessment_templates"
    __table_args__ = (UniqueConstraint("vacancy_id", "version", name="uq_assessment_templates_vacancy_version"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    vacancy_id: Mapped[UUID] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default=TemplateStatus.DRAFT.value)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("TIMEZONE('utc', now())"))

    def to_entity(self) -> AssessmentTemplate:
        return AssessmentTemplate(
            id=self.id,
            vacancy_id=self.vacancy_id,
            version=self.version,
            snapshot=AssessmentTemplateSnapshot.model_validate(self.snapshot),
            status=TemplateStatus(self.status),
            created_by=self.created_by,
            created_at=self.created_at,
        )

    @classmethod
    def from_entity(cls, value: AssessmentTemplate) -> "AssessmentTemplateORM":
        return cls(
            id=value.id,
            vacancy_id=value.vacancy_id,
            version=value.version,
            snapshot=value.snapshot.model_dump(mode="json"),
            status=value.status.value,
            created_by=value.created_by,
        )
