from dataclasses import dataclass

from src.application.dtos.custom_question_draft import CustomQuestionDraft
from src.application.dtos.focus_area_draft import FocusAreaDraft


@dataclass(frozen=True)
class TemplateDraft:
    mode: str
    question_count: int
    duration_minutes: int
    attempt_limit: int
    criteria: tuple[FocusAreaDraft, ...]
    brief: str
    skip: tuple[str, ...]
    red_flags: tuple[str, ...]
    custom_questions: tuple[CustomQuestionDraft, ...]
    language: str
    candidate_feedback: bool
    cv_policy: str
