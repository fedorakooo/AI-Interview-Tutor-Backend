from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class AssessmentCompleted:
    event_id: UUID
    occurred_at: datetime
    correlation_id: UUID
    organization_id: UUID
    vacancy_id: UUID
    invitation_id: UUID
    attempt_id: UUID
    session_id: str
    report_reference: str
    report_version: int = 1
