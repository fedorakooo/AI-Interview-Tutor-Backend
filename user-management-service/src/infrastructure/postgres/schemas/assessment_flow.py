from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.postgres.database import Base


class CandidateInvitationORM(Base):
    __tablename__ = "candidate_invitations"
    __table_args__ = (
        CheckConstraint("status IN ('created', 'opened', 'in_progress', 'completed', 'revoked', 'expired')", name="ck_candidate_invitations_status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    vacancy_id: Mapped[UUID] = mapped_column(ForeignKey("vacancies.id", ondelete="RESTRICT"), index=True)
    template_id: Mapped[UUID] = mapped_column(ForeignKey("assessment_templates.id", ondelete="RESTRICT"))
    template_version: Mapped[int] = mapped_column(Integer)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    candidate_email_normalized: Mapped[str] = mapped_column(String(320))
    expires_at: Mapped[datetime]
    max_attempts: Mapped[int] = mapped_column(Integer, default=1)
    attempts_started: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="created")
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("TIMEZONE('utc', now())"))


class CandidateAttemptORM(Base):
    __tablename__ = "candidate_attempts"
    __table_args__ = (
        CheckConstraint("status IN ('created', 'cv_processing', 'ready', 'in_progress', 'completed', 'failed', 'abandoned')", name="ck_candidate_attempts_status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    invitation_id: Mapped[UUID] = mapped_column(ForeignKey("candidate_invitations.id", ondelete="RESTRICT"), index=True)
    candidate_email_normalized: Mapped[str] = mapped_column(String(320))
    candidate_display_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    consent_version: Mapped[str] = mapped_column(String(64))
    consented_at: Mapped[datetime]
    status: Mapped[str] = mapped_column(String(24), default="created")
    cv_correlation_id: Mapped[UUID | None] = mapped_column(unique=True, nullable=True)
    interview_session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("TIMEZONE('utc', now())"))


class HumanDecisionORM(Base):
    __tablename__ = "human_decisions"
    __table_args__ = (UniqueConstraint("attempt_id", name="uq_human_decisions_attempt"), CheckConstraint("decision IN ('advance', 'hold', 'reject', 'needs_review')", name="ck_human_decisions_decision"))
    id: Mapped[UUID] = mapped_column(primary_key=True)
    attempt_id: Mapped[UUID] = mapped_column(ForeignKey("candidate_attempts.id", ondelete="CASCADE"))
    decision: Mapped[str] = mapped_column(String(24))
    private_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(server_default=text("TIMEZONE('utc', now())"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("TIMEZONE('utc', now())"), onupdate=text("TIMEZONE('utc', now())"))


class AuditLogORM(Base):
    __tablename__ = "audit_log"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    actor_type: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[UUID | None] = mapped_column(nullable=True)
    action: Mapped[str] = mapped_column(String(96))
    organization_id: Mapped[UUID | None] = mapped_column(index=True, nullable=True)
    vacancy_id: Mapped[UUID | None] = mapped_column(nullable=True)
    invitation_id: Mapped[UUID | None] = mapped_column(nullable=True)
    attempt_id: Mapped[UUID | None] = mapped_column(nullable=True)
    before: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    request_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("TIMEZONE('utc', now())"))


class ProcessedEventORM(Base):
    __tablename__ = "processed_events"
    __table_args__ = (UniqueConstraint("consumer_name", "event_id", name="uq_processed_events_consumer_event"),)
    id: Mapped[UUID] = mapped_column(primary_key=True)
    consumer_name: Mapped[str] = mapped_column(String(96))
    event_id: Mapped[UUID] = mapped_column()
    processed_at: Mapped[datetime] = mapped_column(server_default=text("TIMEZONE('utc', now())"))
