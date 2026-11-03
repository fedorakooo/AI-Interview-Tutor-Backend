from dataclasses import dataclass


@dataclass(frozen=True)
class RedFlagDraft:
    flag: str
    quotes: tuple[str, ...]
    reasoning: str
