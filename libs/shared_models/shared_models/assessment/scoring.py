from collections.abc import Sequence

from shared_models.assessment.contracts import FocusArea
from shared_models.assessment.evidence import EvidenceItem, EvidenceLevel, Verdict

LEVEL_POINTS = {EvidenceLevel.STRONG: 2.0, EvidenceLevel.ADEQUATE: 1.0, EvidenceLevel.WEAK: 0.0}
SIGNAL_WEIGHT = 0.25
STRONG_THRESHOLD = 1.5
ADEQUATE_THRESHOLD = 0.75


def compute_focus_verdict(focus: FocusArea, evidence: Sequence[EvidenceItem]) -> tuple[Verdict, float]:
    """Compute the verdict and confidence of a focus area from its evidence."""
    count = len(evidence)
    if count < focus.min_evidence:
        return Verdict.NOT_ASSESSED, round(min(0.4, 0.2 * count), 2)

    strong_hits = sum(1 for item in evidence for signal in item.matched_signals if signal in focus.strong_signals)
    weak_hits = sum(1 for item in evidence for signal in item.matched_signals if signal in focus.weak_signals)
    base = sum(LEVEL_POINTS[item.level] for item in evidence) / count
    value = min(2.0, max(0.0, base + SIGNAL_WEIGHT * (strong_hits - weak_hits) / count))

    if value >= STRONG_THRESHOLD:
        verdict = Verdict.STRONG
    elif value >= ADEQUATE_THRESHOLD:
        verdict = Verdict.ADEQUATE
    else:
        verdict = Verdict.WEAK
    if weak_hits and verdict == Verdict.STRONG:
        verdict = Verdict.ADEQUATE

    confidence = min(0.95, 0.45 + 0.15 * count)
    levels = {item.level for item in evidence}
    if EvidenceLevel.STRONG in levels and EvidenceLevel.WEAK in levels:
        confidence -= 0.15
    return verdict, round(max(0.2, confidence), 2)
