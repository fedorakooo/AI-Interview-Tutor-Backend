from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from jwt_handler.value_objects import AccessTokenPayload
from pydantic import BaseModel, EmailStr, Field
from shared_models.feature_flags.flags import feature_enabled

from src.api.dependencies.database import get_unit_of_work
from src.api.security import require_authenticated, require_org_role
from src.application.use_cases.organizations import (
    AddOrganizationMemberUseCase,
    ChangeOrganizationMemberRoleUseCase,
    CreateOrganizationUseCase,
    DeactivateOrganizationMemberUseCase,
    ListMyOrganizationsUseCase,
)
from src.domain.entities.organization import OrganizationMember
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.value_objects.organization_role import OrganizationRole

router = APIRouter(prefix="/orgs", tags=["Organizations"])


class OrgCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class OrgMemberCreate(BaseModel):
    email: EmailStr
    role: OrganizationRole = OrganizationRole.RECRUITER


class OrgMemberView(BaseModel):
    user_id: UUID
    role: OrganizationRole


class OrgMemberRoleUpdate(BaseModel):
    role: OrganizationRole


class OrgView(BaseModel):
    org_id: UUID
    name: str
    owner_user_id: UUID
    plan: str
    retention_days: int


def _require_feature() -> None:
    if not feature_enabled("EMPLOYER_ASSESSMENT_DEMO", False):
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Employer assessment is disabled")


@router.post("", response_model=OrgView, status_code=status.HTTP_201_CREATED)
async def create_org(
    body: OrgCreate,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
) -> OrgView:
    _require_feature()
    organization = await CreateOrganizationUseCase(uow)(UUID(payload["id"]), body.name)
    return OrgView(
        org_id=organization.id,
        name=organization.name,
        owner_user_id=organization.owner_user_id,
        plan=organization.plan,
        retention_days=organization.retention_days,
    )


@router.get("/mine", response_model=list[OrgView])
async def list_my_orgs(
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
) -> list[OrgView]:
    _require_feature()
    organizations = await ListMyOrganizationsUseCase(uow)(UUID(payload["id"]))
    return [
        OrgView(
            org_id=organization.id,
            name=organization.name,
            owner_user_id=organization.owner_user_id,
            plan=organization.plan,
            retention_days=organization.retention_days,
        )
        for organization in organizations
    ]


@router.post("/{org_id}/members", response_model=OrgMemberView, status_code=status.HTTP_201_CREATED)
async def add_member(
    org_id: UUID,
    body: OrgMemberCreate,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[OrganizationMember, Depends(require_org_role(OrganizationRole.ADMIN))],
) -> OrgMemberView:
    _require_feature()
    member = await AddOrganizationMemberUseCase(uow)(
        organization_id=org_id,
        actor_user_id=UUID(payload["id"]),
        member_email=str(body.email),
        role=body.role,
    )
    return OrgMemberView(user_id=member.user_id, role=member.role)


@router.patch("/{org_id}/members/{member_user_id}", response_model=OrgMemberView)
async def change_member_role(
    org_id: UUID,
    member_user_id: UUID,
    body: OrgMemberRoleUpdate,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[OrganizationMember, Depends(require_org_role(OrganizationRole.ADMIN))],
) -> OrgMemberView:
    _require_feature()
    member = await ChangeOrganizationMemberRoleUseCase(uow)(
        org_id, UUID(payload["id"]), member_user_id, body.role
    )
    return OrgMemberView(user_id=member.user_id, role=member.role)


@router.delete("/{org_id}/members/{member_user_id}", response_model=OrgMemberView)
async def deactivate_member(
    org_id: UUID,
    member_user_id: UUID,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[OrganizationMember, Depends(require_org_role(OrganizationRole.ADMIN))],
) -> OrgMemberView:
    _require_feature()
    member = await DeactivateOrganizationMemberUseCase(uow)(org_id, UUID(payload["id"]), member_user_id)
    return OrgMemberView(user_id=member.user_id, role=member.role)
