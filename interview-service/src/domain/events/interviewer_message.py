from dataclasses import dataclass
from uuid import UUID

from src.domain.enums.message_kind import MessageKind
from src.domain.events.session_event_base import SessionEventBase
from src.domain.exceptions.invalid_value_errors import InvalidDomainValueError


@dataclass(frozen=True, kw_only=True)
class InterviewerMessage(SessionEventBase):
    turn_id: UUID
    kind: MessageKind
    text: str
    focus_id: str | None = None
    custom_question_index: int | None = None

    def __post_init__(self) -> None:
        asks = self.kind in (MessageKind.QUESTION, MessageKind.FOLLOW_UP)
        if asks and self.focus_id is None:
            raise InvalidDomainValueError("Questions must target a focus area")
        if not asks and (self.focus_id is not None or self.custom_question_index is not None):
            raise InvalidDomainValueError("Only questions may reference a focus area")
