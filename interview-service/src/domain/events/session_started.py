from dataclasses import dataclass
from uuid import UUID

from src.domain.events.session_event_base import SessionEventBase


@dataclass(frozen=True, kw_only=True)
class SessionStarted(SessionEventBase):
    attempt_id: UUID
    template_version: int
    cv_attached: bool
