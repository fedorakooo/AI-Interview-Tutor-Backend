from dataclasses import dataclass

from src.domain.entities.session_state import SessionState
from src.domain.enums.verdict import Verdict
from src.domain.value_objects.interview_template import InterviewTemplate


@dataclass(frozen=True)
class AssessmentDigest:
    template: InterviewTemplate
    state: SessionState
    verdicts: dict[str, tuple[Verdict, float]]
