from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.organization import Organization, OrganizationMember
from src.domain.value_objects.organization_role import OrganizationRole
from src.infrastructure.postgres.database import Base


class OrganizationORM(Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    owner_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    plan: Mapped[str] = mapped_column(String(32), default="free")
    retention_days: Mapped[int] = mapped_column(default=365)
    created_at: Mapped[datetime] = mapped_column(server_default=text("TIMEZONE('utc', now())"))
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("TIMEZONE('utc', now())"), onupdate=text("TIMEZONE('utc', now())")
    )

    def to_entity(self) -> Organization:
        return Organization(
            id=self.id,
            name=self.name,
            owner_user_id=self.owner_user_id,
            plan=self.plan,
            retention_days=self.retention_days,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, entity: Organization) -> "OrganizationORM":
        return cls(
            id=entity.id,
            name=entity.name,
            owner_user_id=entity.owner_user_id,
            plan=entity.plan,
            retention_days=entity.retention_days,
        )


class OrganizationMemberORM(Base):
    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_organization_members_organization_user"),
        CheckConstraint("role IN ('admin', 'recruiter', 'hiring_manager')", name="ck_organization_members_role"),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_organization_members_status"),
    )

    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="active")
    invited_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("TIMEZONE('utc', now())"))
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("TIMEZONE('utc', now())"), onupdate=text("TIMEZONE('utc', now())")
    )

    def to_entity(self) -> OrganizationMember:
        return OrganizationMember(
            organization_id=self.organization_id,
            user_id=self.user_id,
            role=OrganizationRole(self.role),
            status=self.status,
            invited_by=self.invited_by,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, entity: OrganizationMember) -> "OrganizationMemberORM":
        return cls(
            organization_id=entity.organization_id,
            user_id=entity.user_id,
            role=entity.role.value,
            status=entity.status,
            invited_by=entity.invited_by,
        )
