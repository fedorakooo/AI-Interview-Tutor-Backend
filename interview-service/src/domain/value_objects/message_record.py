from dataclasses import dataclass
from typing import Literal

from src.domain.enums.message_kind import MessageKind


@dataclass(frozen=True)
class MessageRecord:
    seq: int
    role: Literal["interviewer", "candidate"]
    text: str
    kind: MessageKind | None = None
    focus_id: str | None = None
    custom_question_index: int | None = None
