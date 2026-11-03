from dataclasses import dataclass

from src.domain.value_objects.focus_text import FocusText
from src.domain.value_objects.red_flag_draft import RedFlagDraft


@dataclass(frozen=True)
class AssessmentTexts:
    overall_summary: str
    focus: tuple[FocusText, ...] = ()
    red_flags: tuple[RedFlagDraft, ...] = ()
