from dataclasses import dataclass


@dataclass(frozen=True)
class FocusAreaDraft:
    id: str
    skill: str
    required: bool
    weight: int
    expected_level: str
    guidance: str
    what_to_learn: str
    method: str
    strong_signals: tuple[str, ...]
    weak_signals: tuple[str, ...]
    must_cover: tuple[str, ...]
    min_evidence: int
    max_questions: int
