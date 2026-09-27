from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from jwt_handler.value_objects import AccessTokenPayload
from pydantic import BaseModel, Field
from shared_models.assessment.contracts import AssessmentTemplateSnapshot, VacancyStatus
from shared_models.feature_flags.flags import feature_enabled

from src.api.dependencies.database import get_unit_of_work
from src.api.security import require_authenticated, require_org_role
from src.application.use_cases.vacancies import ActivateVacancyUseCase, CreateVacancyUseCase
from src.domain.entities.organization import OrganizationMember
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.value_objects.organization_role import OrganizationRole

router = APIRouter(prefix="/organizations/{organization_id}/vacancies", tags=["Vacancies"])


class VacancyCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    job_description: str = Field(min_length=1, max_length=20_000)
    seniority: str = Field(min_length=1, max_length=64)
    language: str = Field(min_length=2, max_length=16)
    template: AssessmentTemplateSnapshot


class VacancyView(BaseModel):
    id: UUID
    organization_id: UUID
    title: str
    status: VacancyStatus
    active_template_version: int | None


def _require_feature() -> None:
    if not feature_enabled("EMPLOYER_ASSESSMENT_DEMO", False):
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Employer assessment is disabled")


@router.post("", response_model=VacancyView, status_code=status.HTTP_201_CREATED)
async def create_vacancy(
    organization_id: UUID,
    body: VacancyCreate,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[OrganizationMember, Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.RECRUITER))],
) -> VacancyView:
    _require_feature()
    vacancy = await CreateVacancyUseCase(uow)(
        organization_id=organization_id,
        actor_user_id=UUID(payload["id"]),
        title=body.title,
        job_description=body.job_description,
        seniority=body.seniority,
        language=body.language,
        snapshot=body.template,
    )
    return VacancyView.model_validate(vacancy, from_attributes=True)


@router.post("/{vacancy_id}/activate", response_model=VacancyView)
async def activate_vacancy(
    organization_id: UUID,
    vacancy_id: UUID,
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[OrganizationMember, Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.RECRUITER))],
) -> VacancyView:
    _require_feature()
    vacancy = await ActivateVacancyUseCase(uow)(vacancy_id, organization_id)
    return VacancyView.model_validate(vacancy, from_attributes=True)
