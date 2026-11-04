from uuid import uuid4

import pytest
from src.domain.enums.cv_policy import CvPolicy
from src.domain.enums.evidence_level import EvidenceLevel
from src.domain.enums.verdict import Verdict
from src.domain.services.focus_verdict_calculator import FocusVerdictCalculator
from src.domain.value_objects.evidence_item import EvidenceItem
from src.domain.value_objects.quote_ref import QuoteRef

from tests.fakes.builders import build_template

FOCUS = build_template(CvPolicy.REQUIRED).focus_by_id("databases")


def evidence(level: EvidenceLevel, *signals: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=uuid4(),
        focus_id=FOCUS.id,
        question_seq=1,
        answer_seq=2,
        level=level,
        matched_signals=tuple(signals),
        quotes=(QuoteRef(event_seq=2, start=0, end=3, text="abc"),),
        reasoning="reason",
    )


@pytest.mark.parametrize(
    ("items", "verdict"),
    [
        ([], Verdict.NOT_ASSESSED),
        ([evidence(EvidenceLevel.STRONG)], Verdict.NOT_ASSESSED),
        ([evidence(EvidenceLevel.STRONG), evidence(EvidenceLevel.STRONG)], Verdict.STRONG),
        ([evidence(EvidenceLevel.STRONG), evidence(EvidenceLevel.ADEQUATE)], Verdict.STRONG),
        ([evidence(EvidenceLevel.ADEQUATE), evidence(EvidenceLevel.ADEQUATE)], Verdict.ADEQUATE),
        ([evidence(EvidenceLevel.ADEQUATE), evidence(EvidenceLevel.WEAK)], Verdict.WEAK),
        ([evidence(EvidenceLevel.WEAK), evidence(EvidenceLevel.WEAK)], Verdict.WEAK),
    ],
)
def test_verdict_follows_evidence_levels(items: list[EvidenceItem], verdict: Verdict) -> None:
    assert FocusVerdictCalculator.compute(FOCUS, items)[0] == verdict


def test_matched_weak_signal_caps_a_strong_verdict() -> None:
    items = [evidence(EvidenceLevel.STRONG), evidence(EvidenceLevel.STRONG, FOCUS.weak_signals[0])]

    assert FocusVerdictCalculator.compute(FOCUS, items)[0] == Verdict.ADEQUATE


def test_matched_strong_signals_lift_the_score() -> None:
    plain = [evidence(EvidenceLevel.WEAK), evidence(EvidenceLevel.ADEQUATE)]
    signalled = [
        evidence(EvidenceLevel.WEAK, FOCUS.strong_signals[0]),
        evidence(EvidenceLevel.ADEQUATE, FOCUS.strong_signals[1]),
    ]

    assert FocusVerdictCalculator.compute(FOCUS, plain)[0] == Verdict.WEAK
    assert FocusVerdictCalculator.compute(FOCUS, signalled)[0] == Verdict.ADEQUATE


def test_confidence_grows_with_evidence_and_drops_on_disagreement() -> None:
    agreeing = FocusVerdictCalculator.compute(FOCUS, [evidence(EvidenceLevel.STRONG)] * 2)[1]
    more = FocusVerdictCalculator.compute(FOCUS, [evidence(EvidenceLevel.STRONG)] * 4)[1]
    split = FocusVerdictCalculator.compute(FOCUS, [evidence(EvidenceLevel.STRONG), evidence(EvidenceLevel.WEAK)])[1]

    assert more > agreeing > split
    assert 0 <= FocusVerdictCalculator.compute(FOCUS, [])[1] < 0.5
