from dataclasses import dataclass


@dataclass(frozen=True)
class AssessmentCoverage:
    focus_total: int
    focus_assessed: int
    required_total: int
    required_assessed: int
    questions_asked: int
