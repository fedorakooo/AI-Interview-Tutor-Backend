from dataclasses import dataclass


@dataclass(frozen=True)
class DraftCustomQuestion:
    focus_skill: str
    text: str
    reference_answer: str | None = None
    required: bool = False
