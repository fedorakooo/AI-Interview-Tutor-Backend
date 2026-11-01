from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class VacancyStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class TemplateStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class InvitationStatus(StrEnum):
    CREATED = "created"
    OPENED = "opened"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REVOKED = "revoked"
    EXPIRED = "expired"


class AttemptStatus(StrEnum):
    CREATED = "created"
    CV_PROCESSING = "cv_processing"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


class AssessmentMode(StrEnum):
    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    MIXED = "mixed"


class HumanDecisionType(StrEnum):
    ADVANCE = "advance"
    HOLD = "hold"
    REJECT = "reject"
    NEEDS_REVIEW = "needs_review"


class RubricCriterion(BaseModel):
    skill: str = Field(min_length=1, max_length=120)
    required: bool
    weight: int = Field(ge=1, le=100)
    expected_level: str = Field(min_length=1, max_length=64)
    guidance: str = Field(default="", max_length=1000)


class AssessmentTemplateSnapshot(BaseModel):
    mode: AssessmentMode
    question_count: int = Field(ge=1, le=30)
    duration_minutes: int = Field(ge=5, le=180)
    attempt_limit: int = Field(ge=1, le=5)
    criteria: list[RubricCriterion] = Field(min_length=1)

    @model_validator(mode="after")
    def weights_total_one_hundred(self) -> "AssessmentTemplateSnapshot":
        if sum(criterion.weight for criterion in self.criteria) != 100:
            raise ValueError("Rubric criterion weights must total 100")
        if not any(criterion.required for criterion in self.criteria):
            raise ValueError("At least one rubric criterion must be required")
        return self


class AssessmentEvent(BaseModel):
    event_id: UUID
    schema_version: int = Field(default=1, ge=1)
    occurred_at: datetime
    correlation_id: UUID
    organization_id: UUID
    vacancy_id: UUID
    invitation_id: UUID | None = None
    attempt_id: UUID | None = None


class AssessmentCompleted(AssessmentEvent):
    """Authoritative completion notification emitted by Interview Service.

    The event intentionally contains an opaque report reference only.  It
    must never carry a transcript, rubric scores, candidate email or tokens.
    """

    attempt_id: UUID
    invitation_id: UUID
    session_id: str = Field(min_length=1, max_length=128)
    report_reference: str = Field(min_length=1, max_length=512)
    report_version: int = Field(default=1, ge=1)


class EmployerNotificationRequested(AssessmentEvent):
    """A privacy-safe request for Notification Service to notify an employer.

    Recipient selection remains an authorization concern of User Management;
    this event contains no email address, report body, CV data, or token.
    """

    attempt_id: UUID
    invitation_id: UUID
    notification_type: str = Field(default="assessment_completed", pattern="^assessment_completed$")
    report_version: int = Field(ge=1)


class AssessmentContext(BaseModel):
    """Minimal trusted context handed to Interview Service for one attempt."""

    attempt_id: UUID
    organization_id: UUID
    vacancy_id: UUID
    invitation_id: UUID
    template_version: int = Field(ge=1)
    template: AssessmentTemplateSnapshot
    cv_correlation_id: UUID
    candidate_display_name: str | None = Field(default=None, max_length=160)
