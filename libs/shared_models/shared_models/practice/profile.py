from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from shared_models.practice.exercise import ExerciseType


class DifficultyLevel(StrEnum):
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"


class DevelopmentGoal(BaseModel):
    skill: str
    target_level: DifficultyLevel | None = None
    priority: int = Field(default=1, ge=1, le=5)
    notes: str | None = None


class UserPracticeProfile(BaseModel):
    user_id: UUID
    development_goals: list[DevelopmentGoal] = Field(default_factory=list)
    preferred_difficulty: DifficultyLevel = DifficultyLevel.MID
    preferred_exercise_types: list[ExerciseType] = Field(default_factory=list)
    weekly_target_minutes: int = 60
    daily_plan_quota: int = 3
    plans_generated_today: int = 0
    quota_reset_date: date | None = None
    current_streak_days: int = 0
    last_practice_date: date | None = None
    total_exercises_completed: int = 0
    updated_at: datetime
