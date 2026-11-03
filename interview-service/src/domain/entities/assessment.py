from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.entities.focus_assessment import FocusAssessment
from src.domain.value_objects.assessment_coverage import AssessmentCoverage
from src.domain.value_objects.red_flag_finding import RedFlagFinding


@dataclass(frozen=True)
class Assessment:
    assessment_id: UUID
    attempt_id: UUID
    session_id: str
    template_version: int
    generator_version: str
    generated_at: datetime
    coverage: AssessmentCoverage
    overall_summary: str
    focus: tuple[FocusAssessment, ...]
    report_version: int = 1
    red_flags: tuple[RedFlagFinding, ...] = ()
