from dataclasses import dataclass
from uuid import UUID

from shared_models.assessment import AssessmentContext


@dataclass(frozen=True)
class InterviewConnection:
    attempt_id: UUID
    context: AssessmentContext
