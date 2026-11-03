from dataclasses import dataclass


@dataclass(frozen=True)
class CustomQuestionDraft:
    focus_id: str
    text: str
    reference_answer: str | None
    required: bool
