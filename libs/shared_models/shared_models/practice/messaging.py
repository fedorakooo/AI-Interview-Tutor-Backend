from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from shared_models.practice.exercise import ExerciseType
from shared_models.practice.plan import PlanSource
from shared_models.practice.profile import DifficultyLevel


class PlanGenerationRequest(BaseModel):
    focus_skills: list[str] = Field(default_factory=list)
    difficulty: DifficultyLevel = DifficultyLevel.MID
    exercise_types: list[ExerciseType] = Field(default_factory=list)
    exercise_count: int = 8
    include_interview_context: bool = True
    include_cv_context: bool = True
    title_hint: str | None = None


class PracticePlanJobMessage(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    job_id: UUID
    plan_id: UUID
    user_id: UUID
    source: PlanSource
    request: PlanGenerationRequest
    interview_session_id: str | None = None
    cv_correlation_id: str | None = None
    published_at: datetime

    @field_validator("published_at", mode="before")
    @classmethod
    def _parse_published_at(cls, value: datetime | str) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        return datetime.fromisoformat(value)


class InterviewCompletedEvent(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    event_id: UUID
    user_id: UUID
    session_id: str
    cv_correlation_id: str | None = None
    published_at: datetime

    @field_validator("published_at", mode="before")
    @classmethod
    def _parse_published_at(cls, value: datetime | str) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        return datetime.fromisoformat(value)


class PracticePlanReadyEvent(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    event_id: UUID
    plan_id: UUID
    user_id: UUID
    plan_title: str
    exercise_count: int
    source: PlanSource
    published_at: datetime

    @field_validator("published_at", mode="before")
    @classmethod
    def _parse_published_at(cls, value: datetime | str) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        return datetime.fromisoformat(value)
