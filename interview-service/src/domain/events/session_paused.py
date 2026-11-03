from dataclasses import dataclass

from src.domain.enums.pause_reason import PauseReason
from src.domain.events.session_event_base import SessionEventBase


@dataclass(frozen=True, kw_only=True)
class SessionPaused(SessionEventBase):
    reason: PauseReason
