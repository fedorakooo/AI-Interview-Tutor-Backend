from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ExerciseType(StrEnum):
    MCQ_SINGLE = "mcq_single"
    MCQ_MULTI = "mcq_multi"
    OPEN_QUESTION = "open_question"
    FLASHCARD = "flashcard"
    CODE_REVIEW = "code_review"
    SCENARIO = "scenario"


class FlashcardRating(StrEnum):
    AGAIN = "again"
    GOOD = "good"
    EASY = "easy"


class Choice(BaseModel):
    choice_id: str
    text: str
    is_correct: bool = False


class Exercise(BaseModel):
    exercise_id: str
    type: ExerciseType
    skill_tags: list[str] = Field(default_factory=list)
    difficulty: DifficultyLevel
    title: str
    prompt: str
    choices: list[Choice] | None = None
    hint: str | None = None
    max_answer_chars: int | None = None
    rubric_bullets: list[str] = Field(default_factory=list)
    reference_answer: str | None = None
    code_snippet: str | None = None
    code_language: str | None = None
    scenario_tasks: list[str] = Field(default_factory=list)
    explanation: str | None = None
    estimated_minutes: int = 3


from shared_models.practice.profile import DifficultyLevel  # noqa: E402

Exercise.model_rebuild()
