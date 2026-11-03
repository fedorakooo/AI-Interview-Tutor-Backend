from dataclasses import dataclass

from src.domain.enums.focus_method import FocusMethod


@dataclass(frozen=True)
class DraftFocus:
    skill: str
    what_to_learn: str = ""
    required: bool = False
    weight: int = 1
    expected_level: str = "middle"
    guidance: str = ""
    method: FocusMethod = FocusMethod.QUESTIONS
    strong_signals: tuple[str, ...] = ()
    weak_signals: tuple[str, ...] = ()
    must_cover: tuple[str, ...] = ()
    min_evidence: int = 2
    max_questions: int = 3
