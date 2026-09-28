from typing import Annotated
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from jwt_handler.value_objects import AccessTokenPayload
from pydantic import BaseModel, Field
from shared_models.assessment.contracts import AssessmentTemplateSnapshot, VacancyStatus
from shared_models.feature_flags.flags import feature_enabled

from src.api.dependencies.database import get_unit_of_work
from src.api.dependencies.assessment import get_invitation_token_handler
from src.api.security import require_authenticated, require_org_role
from src.application.use_cases.vacancies import (
    ActivateVacancyUseCase,
    CreateVacancyUseCase,
    GetVacancyUseCase,
    ListVacanciesUseCase,
    ReplaceTemplateUseCase,
    UpdateVacancyUseCase,
)
from src.domain.entities.organization import OrganizationMember
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.value_objects.organization_role import OrganizationRole
from src.application.use_cases.assessments import CreateInvitationUseCase, RevokeInvitationUseCase
from src.infrastructure.auth.invitation_token_handler import InvitationTokenHandler

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


class VacancyUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    job_description: str | None = Field(default=None, min_length=1, max_length=20_000)
    seniority: str | None = Field(default=None, min_length=1, max_length=64)
    language: str | None = Field(default=None, min_length=2, max_length=16)


class InvitationCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class InvitationView(BaseModel):
    id: UUID
    status: str
    expires_at: datetime
    attempts_started: int


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


@router.get("", response_model=list[VacancyView])
async def list_vacancies(
    organization_id: UUID,
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[
        OrganizationMember,
        Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.RECRUITER, OrganizationRole.HIRING_MANAGER)),
    ],
) -> list[VacancyView]:
    _require_feature()
    vacancies = await ListVacanciesUseCase(uow)(organization_id)
    return [VacancyView.model_validate(vacancy, from_attributes=True) for vacancy in vacancies]


@router.get("/{vacancy_id}", response_model=VacancyView)
async def get_vacancy(
    organization_id: UUID,
    vacancy_id: UUID,
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[
        OrganizationMember,
        Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.RECRUITER, OrganizationRole.HIRING_MANAGER)),
    ],
) -> VacancyView:
    _require_feature()
    vacancy = await GetVacancyUseCase(uow)(vacancy_id, organization_id)
    return VacancyView.model_validate(vacancy, from_attributes=True)


@router.patch("/{vacancy_id}", response_model=VacancyView)
async def update_vacancy(
    organization_id: UUID,
    vacancy_id: UUID,
    body: VacancyUpdate,
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[OrganizationMember, Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.RECRUITER))],
) -> VacancyView:
    _require_feature()
    vacancy = await UpdateVacancyUseCase(uow)(vacancy_id, organization_id, body.model_dump(exclude_none=True))
    return VacancyView.model_validate(vacancy, from_attributes=True)


@router.put("/{vacancy_id}/template", response_model=VacancyView)
async def replace_template(
    organization_id: UUID,
    vacancy_id: UUID,
    snapshot: AssessmentTemplateSnapshot,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[OrganizationMember, Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.RECRUITER))],
) -> VacancyView:
    _require_feature()
    vacancy = await ReplaceTemplateUseCase(uow)(
        vacancy_id=vacancy_id,
        organization_id=organization_id,
        actor_user_id=UUID(payload["id"]),
        snapshot=snapshot,
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


@router.post("/{vacancy_id}/invitations", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    organization_id: UUID, vacancy_id: UUID, body: InvitationCreate,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    tokens: Annotated[InvitationTokenHandler, Depends(get_invitation_token_handler)],
    _: Annotated[OrganizationMember, Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.RECRUITER))],
) -> dict:
    _require_feature()
    invitation, raw_token = await CreateInvitationUseCase(uow, tokens)(organization_id, vacancy_id, UUID(payload["id"]), body.email)
    # The raw secret exists in exactly this create response; persistence and later views have only its digest.
    return {"id": str(invitation.id), "status": invitation.status, "expires_at": invitation.expires_at.isoformat(), "invitation_token": raw_token}


@router.get("/{vacancy_id}/invitations", response_model=list[InvitationView])
async def list_invitations(
    organization_id: UUID, vacancy_id: UUID,
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[OrganizationMember, Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.RECRUITER))],
) -> list[InvitationView]:
    _require_feature()
    async with uow:
        invitations = await uow.assessment_repository.list_invitations(organization_id, vacancy_id)
    return [InvitationView(id=item.id, status=item.status, expires_at=item.expires_at, attempts_started=item.attempts_started) for item in invitations]


@router.post("/{vacancy_id}/invitations/{invitation_id}/revoke", response_model=InvitationView)
async def revoke_invitation(
    organization_id: UUID, vacancy_id: UUID, invitation_id: UUID,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[OrganizationMember, Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.RECRUITER))],
) -> InvitationView:
    _require_feature()
    invitation = await RevokeInvitationUseCase(uow)(organization_id, invitation_id, UUID(payload["id"]))
    return InvitationView(id=invitation.id, status=invitation.status, expires_at=invitation.expires_at, attempts_started=invitation.attempts_started)
