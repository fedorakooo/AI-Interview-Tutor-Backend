from dataclasses import dataclass

from src.domain.enums.assessment_mode import AssessmentMode
from src.domain.enums.cv_policy import CvPolicy
from src.domain.exceptions.invalid_value_errors import InvalidDomainValueError
from src.domain.value_objects.custom_question import CustomQuestion
from src.domain.value_objects.focus_area import FocusArea


@dataclass(frozen=True)
class InterviewTemplate:
    mode: AssessmentMode
    question_count: int
    duration_minutes: int
    attempt_limit: int
    criteria: tuple[FocusArea, ...]
    brief: str = ""
    skip: tuple[str, ...] = ()
    red_flags: tuple[str, ...] = ()
    custom_questions: tuple[CustomQuestion, ...] = ()
    language: str = "en"
    candidate_feedback: bool = False
    cv_policy: CvPolicy = CvPolicy.REQUIRED

    def __post_init__(self) -> None:
        if sum(criterion.weight for criterion in self.criteria) != 100:
            raise InvalidDomainValueError("Rubric criterion weights must total 100")
        if not any(criterion.required for criterion in self.criteria):
            raise InvalidDomainValueError("At least one rubric criterion must be required")
        ids = [focus.id for focus in self.criteria]
        if len(set(ids)) != len(ids):
            raise InvalidDomainValueError("Focus area ids must be unique")
        if {question.focus_id for question in self.custom_questions} - set(ids):
            raise InvalidDomainValueError("Custom questions reference unknown focus ids")

    def focus_by_id(self, focus_id: str) -> FocusArea:
        for focus in self.criteria:
            if focus.id == focus_id:
                return focus
        raise KeyError(focus_id)
