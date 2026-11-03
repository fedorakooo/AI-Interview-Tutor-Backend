from dataclasses import dataclass
from uuid import UUID

from src.domain.value_objects.assessment_context import AssessmentContext


@dataclass(frozen=True)
class InterviewConnection:
    attempt_id: UUID
    context: AssessmentContext

    @property
    def language(self) -> str:
        return self.context.template.language

    @property
    def question_count(self) -> int:
        return self.context.template.question_count

    @property
    def duration_minutes(self) -> int:
        return self.context.template.duration_minutes
