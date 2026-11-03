from dataclasses import dataclass

from src.domain.enums.completion_reason import CompletionReason
from src.domain.events.session_event_base import SessionEventBase


@dataclass(frozen=True, kw_only=True)
class SessionCompleted(SessionEventBase):
    reason: CompletionReason
