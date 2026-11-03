from dataclasses import dataclass

from src.domain.value_objects.focus_area import FocusArea
from src.domain.value_objects.interview_template import InterviewTemplate


@dataclass(frozen=True)
class EvaluationRequest:
    template: InterviewTemplate
    target_focus: FocusArea
    question_text: str
    answer_text: str
