from dataclasses import dataclass
from uuid import UUID

from src.domain.enums.cv_policy import CvPolicy
from src.domain.exceptions.invalid_value_errors import InvalidDomainValueError
from src.domain.value_objects.interview_template import InterviewTemplate


@dataclass(frozen=True)
class AssessmentContext:
    attempt_id: UUID
    organization_id: UUID
    vacancy_id: UUID
    invitation_id: UUID
    template_version: int
    template: InterviewTemplate
    cv_policy: CvPolicy = CvPolicy.REQUIRED
    cv_correlation_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.cv_policy != self.template.cv_policy:
            raise InvalidDomainValueError("Context cv_policy must match the template cv_policy")
        if self.cv_policy == CvPolicy.REQUIRED and self.cv_correlation_id is None:
            raise InvalidDomainValueError("cv_correlation_id is required when cv_policy is required")
