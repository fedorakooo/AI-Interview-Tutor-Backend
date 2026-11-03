from uuid import uuid4

import pytest
from shared_models.assessment import (
    CvPolicy,
    EvidenceItem,
    EvidenceLevel,
    QuoteRef,
    Verdict,
    build_focus_detail,
    build_overview,
    compute_focus_verdict,
    fold_events,
)
from shared_models.assessment.mocks import mock_assessment, mock_session_events, mock_template

FOCUS = mock_template().focus_by_id("databases")


def evidence(level: EvidenceLevel, *signals: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=uuid4(),
        focus_id=FOCUS.id,
        question_seq=1,
        answer_seq=2,
        level=level,
        matched_signals=list(signals),
        quotes=[QuoteRef(event_seq=2, start=0, end=3, text="abc")],
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
    assert compute_focus_verdict(FOCUS, items)[0] == verdict


def test_matched_weak_signal_caps_a_strong_verdict() -> None:
    items = [evidence(EvidenceLevel.STRONG), evidence(EvidenceLevel.STRONG, FOCUS.weak_signals[0])]

    assert compute_focus_verdict(FOCUS, items)[0] == Verdict.ADEQUATE


def test_matched_strong_signals_lift_the_score() -> None:
    plain = [evidence(EvidenceLevel.WEAK), evidence(EvidenceLevel.ADEQUATE)]
    signalled = [
        evidence(EvidenceLevel.WEAK, FOCUS.strong_signals[0]),
        evidence(EvidenceLevel.ADEQUATE, FOCUS.strong_signals[1]),
    ]

    assert compute_focus_verdict(FOCUS, plain)[0] == Verdict.WEAK
    assert compute_focus_verdict(FOCUS, signalled)[0] == Verdict.ADEQUATE


def test_confidence_grows_with_evidence_and_drops_on_disagreement() -> None:
    agreeing = compute_focus_verdict(FOCUS, [evidence(EvidenceLevel.STRONG)] * 2)[1]
    more = compute_focus_verdict(FOCUS, [evidence(EvidenceLevel.STRONG)] * 4)[1]
    split = compute_focus_verdict(FOCUS, [evidence(EvidenceLevel.STRONG), evidence(EvidenceLevel.WEAK)])[1]

    assert more > agreeing > split
    assert 0 <= compute_focus_verdict(FOCUS, [])[1] < 0.5


@pytest.mark.parametrize("policy", [CvPolicy.REQUIRED, CvPolicy.NONE])
class TestViews:
    def test_overview_has_no_quotes_and_carries_importance(self, policy: CvPolicy) -> None:
        overview = build_overview(mock_assessment(policy), mock_template(policy))

        dumped = overview.model_dump_json()
        assert '"quotes"' not in dumped and '"text"' not in dumped
        by_id = {item.focus_id: item for item in overview.focus}
        assert by_id["databases"].required is True and by_id["databases"].weight == 25
        assert by_id["databases"].matched_weak_signals
        assert by_id["testing"].verdict == Verdict.NOT_ASSESSED
        assert overview.red_flags[0].flag

    def test_focus_detail_builds_the_timeline_from_the_journal(self, policy: CvPolicy) -> None:
        events = mock_session_events(policy)
        detail = build_focus_detail(mock_assessment(policy), mock_template(policy), fold_events(events), "databases")

        assert [entry.custom_question for entry in detail.timeline] == [True, False]
        assert all(entry.evidence is not None for entry in detail.timeline)
        assert detail.timeline[0].answer_text.startswith("First I'd get the actual plan")
        assert detail.reference_answer and "EXPLAIN" in detail.reference_answer
        assert detail.focus.focus_id == "databases"

    def test_focus_without_a_custom_question_has_no_reference(self, policy: CvPolicy) -> None:
        detail = build_focus_detail(
            mock_assessment(policy), mock_template(policy), fold_events(mock_session_events(policy)), "api_design"
        )

        assert detail.reference_answer is None
