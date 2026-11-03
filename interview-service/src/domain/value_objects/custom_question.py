from dataclasses import dataclass


@dataclass(frozen=True)
class CustomQuestion:
    focus_id: str
    text: str
    reference_answer: str | None = None
    required: bool = False
