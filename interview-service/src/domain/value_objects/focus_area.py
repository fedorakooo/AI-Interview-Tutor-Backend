from dataclasses import dataclass

from src.domain.enums.focus_method import FocusMethod
from src.domain.exceptions.invalid_value_errors import InvalidDomainValueError


@dataclass(frozen=True)
class FocusArea:
    id: str
    skill: str
    required: bool
    weight: int
    expected_level: str
    guidance: str = ""
    what_to_learn: str = ""
    method: FocusMethod = FocusMethod.QUESTIONS
    strong_signals: tuple[str, ...] = ()
    weak_signals: tuple[str, ...] = ()
    must_cover: tuple[str, ...] = ()
    min_evidence: int = 1
    max_questions: int = 3

    def __post_init__(self) -> None:
        if not self.id or not self.skill.strip():
            raise InvalidDomainValueError("Focus area needs an id and a skill")
        if self.min_evidence > self.max_questions:
            raise InvalidDomainValueError("min_evidence must not exceed max_questions")
