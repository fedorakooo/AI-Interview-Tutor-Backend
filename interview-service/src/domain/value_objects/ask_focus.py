from dataclasses import dataclass

from src.domain.enums.message_kind import MessageKind


@dataclass(frozen=True)
class AskFocus:
    focus_id: str
    kind: MessageKind
    custom_question_index: int | None = None
