from dataclasses import dataclass

from src.domain.enums.completion_reason import CompletionReason


@dataclass(frozen=True)
class Complete:
    reason: CompletionReason
