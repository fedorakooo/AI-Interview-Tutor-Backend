from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.value_objects.organization_role import OrganizationRole


@dataclass
class Organization:
    id: UUID
    name: str
    owner_user_id: UUID
    plan: str
    retention_days: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class OrganizationMember:
    organization_id: UUID
    user_id: UUID
    role: OrganizationRole
    status: str = "active"
    invited_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
