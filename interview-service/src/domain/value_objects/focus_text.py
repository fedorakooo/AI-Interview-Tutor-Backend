from dataclasses import dataclass


@dataclass(frozen=True)
class FocusText:
    focus_id: str
    summary_short: str
    rationale: str
    reference_comparison: str | None = None
