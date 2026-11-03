from dataclasses import dataclass

from src.domain.enums.assessment_mode import AssessmentMode
from src.domain.value_objects.draft_custom_question import DraftCustomQuestion
from src.domain.value_objects.draft_focus import DraftFocus


@dataclass(frozen=True)
class SpecDraft:
    mode: AssessmentMode = AssessmentMode.MIXED
    question_count: int = 10
    duration_minutes: int = 45
    focus_areas: tuple[DraftFocus, ...] = ()
    skip: tuple[str, ...] = ()
    red_flags: tuple[str, ...] = ()
    custom_questions: tuple[DraftCustomQuestion, ...] = ()
