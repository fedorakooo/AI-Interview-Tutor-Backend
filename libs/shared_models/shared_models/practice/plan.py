from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from shared_models.interview.report import SkillScore
from shared_models.practice.exercise import Exercise, ExerciseType
from shared_models.practice.profile import DifficultyLevel


class PlanSource(StrEnum):
    MANUAL = "manual"
    INTERVIEW = "interview"
    CV = "cv"
    COMBINED = "combined"


class PlanStatus(StrEnum):
    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"
    ARCHIVED = "archived"


class PlanContextSnapshot(BaseModel):
    focus_skills: list[str]
    cv_specialization: str | None = None
    cv_top_skills: list[str] = Field(default_factory=list)
    interview_weaknesses: list[str] = Field(default_factory=list)
    interview_low_scores: list[SkillScore] = Field(default_factory=list)
    user_goals: list[str] = Field(default_factory=list)
    difficulty: DifficultyLevel
    exercise_types_requested: list[ExerciseType] = Field(default_factory=list)


class PracticePlan(BaseModel):
    plan_id: UUID
    user_id: UUID
    source: PlanSource
    status: PlanStatus
    title: str
    focus_skills: list[str]
    difficulty: DifficultyLevel
    exercises: list[Exercise] = Field(default_factory=list)
    context_snapshot: PlanContextSnapshot
    interview_session_id: str | None = None
    cv_correlation_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    exercise_count: int = 0
    created_at: datetime
    updated_at: datetime
    ready_at: datetime | None = None


class PracticePlanDraft(BaseModel):
    title: str
    focus_skills: list[str]
    exercises: list[Exercise]
