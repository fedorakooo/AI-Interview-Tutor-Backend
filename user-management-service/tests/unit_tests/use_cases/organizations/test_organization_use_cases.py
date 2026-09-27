from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.application.use_cases.organizations import AddOrganizationMemberUseCase, CreateOrganizationUseCase
from src.domain.exceptions.organization_errors import OrganizationAccessError
from src.domain.value_objects.organization_role import OrganizationRole


class FakeOrganizationRepository:
    def __init__(self):
        self.organizations = {}
        self.members = {}

    async def create(self, organization):
        self.organizations[organization.id] = organization
        return organization

    async def create_member(self, member):
        key = (member.organization_id, member.user_id)
        if key in self.members:
            raise ValueError("duplicate membership")
        self.members[key] = member
        return member

    async def get_member(self, organization_id, user_id):
        return self.members.get((organization_id, user_id))


class FakeUserRepository:
    def __init__(self, users):
        self.users = users

    async def get_by_email(self, email):
        return self.users.get(email)


class FakeUow:
    def __init__(self, organization_repository, user_repository):
        self.organization_repository = organization_repository
        self.user_repository = user_repository

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None


@pytest.mark.asyncio
async def test_create_organization_makes_owner_an_admin_member():
    owner_id = uuid4()
    organizations = FakeOrganizationRepository()
    uow = FakeUow(organizations, FakeUserRepository({}))

    organization = await CreateOrganizationUseCase(uow)(owner_id, "  Acme  ")

    assert organization.name == "Acme"
    owner_membership = organizations.members[(organization.id, owner_id)]
    assert owner_membership.role == OrganizationRole.ADMIN
    assert owner_membership.invited_by == owner_id


@pytest.mark.asyncio
async def test_only_org_admin_can_add_a_member():
    organization_id, recruiter_id, candidate_id = uuid4(), uuid4(), uuid4()
    organizations = FakeOrganizationRepository()
    await organizations.create_member(
        SimpleNamespace(
            organization_id=organization_id,
            user_id=recruiter_id,
            role=OrganizationRole.RECRUITER,
            status="active",
        )
    )
    uow = FakeUow(organizations, FakeUserRepository({"candidate@example.com": SimpleNamespace(id=candidate_id)}))

    with pytest.raises(OrganizationAccessError):
        await AddOrganizationMemberUseCase(uow)(
            organization_id, recruiter_id, "candidate@example.com", OrganizationRole.HIRING_MANAGER
        )
