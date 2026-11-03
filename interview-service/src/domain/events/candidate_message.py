from dataclasses import dataclass
from uuid import UUID

from src.domain.events.session_event_base import SessionEventBase


@dataclass(frozen=True, kw_only=True)
class CandidateMessage(SessionEventBase):
    turn_id: UUID
    text: str
