from dataclasses import dataclass

from src.domain.exceptions.invalid_value_errors import InvalidDomainValueError


@dataclass(frozen=True)
class QuoteRef:
    event_seq: int
    start: int
    end: int
    text: str

    def __post_init__(self) -> None:
        if self.event_seq < 1 or self.start < 0 or self.end <= self.start:
            raise InvalidDomainValueError("Quote span is invalid")
        if not self.text or len(self.text) != self.end - self.start:
            raise InvalidDomainValueError("Quote text length must match the span")
