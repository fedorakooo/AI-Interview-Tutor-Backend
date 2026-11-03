from dataclasses import dataclass

from src.domain.value_objects.candidate_cv import CandidateCv
from src.domain.value_objects.custom_question import CustomQuestion
from src.domain.value_objects.focus_area import FocusArea
from src.domain.value_objects.focus_coverage import FocusCoverage
from src.domain.value_objects.interview_template import InterviewTemplate
from src.domain.value_objects.message_record import MessageRecord
from src.domain.value_objects.next_action import NextAction


@dataclass(frozen=True)
class InterviewerRequest:
    template: InterviewTemplate
    action: NextAction
    focus: FocusArea | None = None
    custom_question: CustomQuestion | None = None
    coverage: FocusCoverage | None = None
    cv: CandidateCv | None = None
    transcript: tuple[MessageRecord, ...] = ()
