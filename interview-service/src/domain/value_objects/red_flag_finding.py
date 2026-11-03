from dataclasses import dataclass

from src.domain.value_objects.quote_ref import QuoteRef


@dataclass(frozen=True)
class RedFlagFinding:
    flag: str
    quotes: tuple[QuoteRef, ...]
    reasoning: str
