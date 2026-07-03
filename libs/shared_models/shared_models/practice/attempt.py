from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from shared_models.practice.exercise import ExerciseType, FlashcardRating


class AttemptStatus(StrEnum):
    SUBMITTED = "submitted"
    GRADED = "graded"
    SKIPPED = "skipped"


class GradingResult(BaseModel):
    score: float = Field(ge=0, le=10)
    is_correct: bool | None = None
    feedback: str
    key_points_missed: list[str] = Field(default_factory=list)
    graded_by: Literal["deterministic", "llm", "self"] = "deterministic"


class ExerciseAttempt(BaseModel):
    attempt_id: UUID
    plan_id: UUID
    exercise_id: str
    user_id: UUID
    exercise_type: ExerciseType
    answer: dict[str, Any]
    flashcard_rating: FlashcardRating | None = None
    status: AttemptStatus
    grading: GradingResult | None = None
    submitted_at: datetime
    graded_at: datetime | None = None
