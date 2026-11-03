from dataclasses import dataclass

from src.domain.events.session_event_base import SessionEventBase


@dataclass(frozen=True, kw_only=True)
class SessionFailed(SessionEventBase):
    error_code: str
