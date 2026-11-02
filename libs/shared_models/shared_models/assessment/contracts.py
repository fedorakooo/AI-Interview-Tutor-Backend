import re
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

TEMPLATE_SCHEMA_VERSION = 2
FOCUS_ID_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,63}$"
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


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


class CvPolicy(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    NONE = "none"


class FocusMethod(StrEnum):
    QUESTIONS = "questions"
    PROBE = "probe"
    STAR = "star"


class FocusArea(RubricCriterion):
    """One thing the recruiter wants to learn, with an id stable across template versions."""

    id: str = Field(pattern=FOCUS_ID_PATTERN)
    what_to_learn: str = Field(default="", max_length=1000)
    method: FocusMethod = FocusMethod.QUESTIONS
    strong_signals: list[ShortText] = Field(default_factory=list, max_length=10)
    weak_signals: list[ShortText] = Field(default_factory=list, max_length=10)
    must_cover: list[ShortText] = Field(default_factory=list, max_length=10)
    min_evidence: int = Field(default=1, ge=1, le=5)
    max_questions: int = Field(default=3, ge=1, le=10)

    @field_validator("skill")
    @classmethod
    def skill_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Focus area skill must not be blank")
        return value

    @model_validator(mode="after")
    def evidence_fits_question_budget(self) -> "FocusArea":
        if self.min_evidence > self.max_questions:
            raise ValueError("min_evidence must not exceed max_questions")
        return self


class CustomQuestion(BaseModel):
    focus_id: str = Field(pattern=FOCUS_ID_PATTERN)
    text: str = Field(min_length=1, max_length=1000)
    reference_answer: str | None = Field(default=None, max_length=2000)
    required: bool = False


def slugify_focus_id(skill: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", skill.lower()).strip("_")[:48]
    return slug or "focus"


def upcast_template_v1(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Lift a version 1 template payload to version 2 with ids derived from skill names."""
    data = dict(payload)
    used: set[str] = set()
    criteria: list[dict[str, Any]] = []
    for raw in data.get("criteria") or []:
        item = raw.model_dump() if isinstance(raw, BaseModel) else dict(raw)
        if not item.get("id"):
            base = slugify_focus_id(str(item.get("skill", "")))
            candidate, suffix = base, 2
            while candidate in used:
                candidate, suffix = f"{base}_{suffix}", suffix + 1
            item["id"] = candidate
        used.add(item["id"])
        if not item.get("what_to_learn"):
            item["what_to_learn"] = item.get("guidance") or item.get("skill") or ""
        criteria.append(item)
    if "criteria" in data:
        data["criteria"] = criteria
    data["schema_version"] = TEMPLATE_SCHEMA_VERSION
    data.setdefault("cv_policy", CvPolicy.REQUIRED)
    return data


class AssessmentTemplateSnapshot(BaseModel):
    """Interview specification that upcasts version 1 payloads on validation."""

    schema_version: Literal[2] = TEMPLATE_SCHEMA_VERSION
    mode: AssessmentMode
    question_count: int = Field(ge=1, le=30)
    duration_minutes: int = Field(ge=5, le=180)
    attempt_limit: int = Field(ge=1, le=5)
    criteria: list[FocusArea] = Field(min_length=1)
    brief: str = Field(default="", max_length=8000)
    skip: list[ShortText] = Field(default_factory=list, max_length=20)
    red_flags: list[ShortText] = Field(default_factory=list, max_length=20)
    custom_questions: list[CustomQuestion] = Field(default_factory=list, max_length=20)
    language: str = Field(default="en", pattern=r"^[a-z]{2,3}(-[A-Za-z]{2,4})?$")
    candidate_feedback: bool = False
    cv_policy: CvPolicy = CvPolicy.REQUIRED

    @model_validator(mode="before")
    @classmethod
    def upcast_legacy_payload(cls, data: Any) -> Any:
        if isinstance(data, Mapping) and data.get("schema_version", 1) == 1:
            return upcast_template_v1(data)
        return data

    @model_validator(mode="after")
    def weights_total_one_hundred(self) -> "AssessmentTemplateSnapshot":
        if sum(criterion.weight for criterion in self.criteria) != 100:
            raise ValueError("Rubric criterion weights must total 100")
        if not any(criterion.required for criterion in self.criteria):
            raise ValueError("At least one rubric criterion must be required")
        return self

    @model_validator(mode="after")
    def focus_references_are_valid(self) -> "AssessmentTemplateSnapshot":
        ids = [focus.id for focus in self.criteria]
        if len(set(ids)) != len(ids):
            raise ValueError("Focus area ids must be unique")
        unknown = {question.focus_id for question in self.custom_questions} - set(ids)
        if unknown:
            raise ValueError(f"Custom questions reference unknown focus ids: {sorted(unknown)}")
        return self

    @property
    def focus_areas(self) -> list[FocusArea]:
        return self.criteria

    def focus_by_id(self, focus_id: str) -> FocusArea:
        for focus in self.criteria:
            if focus.id == focus_id:
                return focus
        raise KeyError(focus_id)


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

    schema_version: int = Field(default=2, ge=1)
    attempt_id: UUID
    organization_id: UUID
    vacancy_id: UUID
    invitation_id: UUID
    template_version: int = Field(ge=1)
    template: AssessmentTemplateSnapshot
    cv_correlation_id: UUID | None = None
    candidate_display_name: str | None = Field(default=None, max_length=160)
    job_description: str | None = Field(default=None, max_length=20000)
    brief: str | None = Field(default=None, max_length=8000)
    cv_policy: CvPolicy = CvPolicy.REQUIRED

    @model_validator(mode="before")
    @classmethod
    def inherit_cv_policy_from_template(cls, data: Any) -> Any:
        if not isinstance(data, Mapping) or data.get("cv_policy") is not None:
            return data
        template = data.get("template")
        if isinstance(template, AssessmentTemplateSnapshot):
            policy = template.cv_policy
        elif isinstance(template, Mapping):
            policy = template.get("cv_policy", CvPolicy.REQUIRED)
        else:
            return data
        return {**data, "cv_policy": policy}

    @model_validator(mode="after")
    def cv_reference_matches_policy(self) -> "AssessmentContext":
        if self.cv_policy != self.template.cv_policy:
            raise ValueError("Context cv_policy must match the template cv_policy")
        if self.cv_policy == CvPolicy.REQUIRED and self.cv_correlation_id is None:
            raise ValueError("cv_correlation_id is required when cv_policy is required")
        return self
