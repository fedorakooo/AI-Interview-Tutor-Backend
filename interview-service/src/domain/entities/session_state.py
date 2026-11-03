from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

from src.domain.enums.completion_reason import CompletionReason
from src.domain.enums.session_status import SessionStatus
from src.domain.value_objects.evidence_item import EvidenceItem
from src.domain.value_objects.focus_coverage import FocusCoverage
from src.domain.value_objects.message_record import MessageRecord


@dataclass
class SessionState:
    session_id: str
    attempt_id: UUID
    template_version: int
    cv_attached: bool
    started_at: datetime
    last_seq: int
    last_event_id: UUID
    status: SessionStatus = SessionStatus.IN_PROGRESS
    messages: dict[int, MessageRecord] = field(default_factory=dict)
    evidence: list[EvidenceItem] = field(default_factory=list)
    coverage: dict[str, FocusCoverage] = field(default_factory=dict)
    questions_asked: int = 0
    completion_reason: CompletionReason | None = None
    failure_code: str | None = None
    paused_at: datetime | None = None
    paused_seconds: float = 0.0

    def active_elapsed(self, now: datetime) -> timedelta:
        paused = self.paused_seconds
        if self.paused_at is not None:
            paused += (now - self.paused_at).total_seconds()
        return max(timedelta(), now - self.started_at - timedelta(seconds=paused))
