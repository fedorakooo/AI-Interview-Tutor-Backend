import pytest
from pydantic import ValidationError
from shared_models.assessment import FocusDetail

EVIDENCE = {
    "evidence_id": "6f1c2a4e-0b7d-4c1a-9a55-3d2f8e6b7c11",
    "focus_id": "python_core",
    "question_seq": 2,
    "answer_seq": 3,
    "level": "strong",
    "matched_signals": ["Explains GIL impact"],
    "quotes": [{"event_seq": 3, "start": 4, "end": 7, "text": "GIL"}],
    "reasoning": "Clear explanation.",
}
REVIEW = {
    "review_id": "6f1c2a4e-0b7d-4c1a-9a55-3d2f8e6b7c12",
    "author_id": "6f1c2a4e-0b7d-4c1a-9a55-3d2f8e6b7c13",
    "created_at": "2026-11-02T10:00:00Z",
    "comment": "Agree.",
    "manual_verdict": "weak",
}
FOCUS = {
    "focus_id": "python_core",
    "verdict": "strong",
    "confidence": 0.8,
    "summary_short": "Solid.",
    "rationale": "Good answers.",
    "evidence": [EVIDENCE],
    "covered_must_cover": ["GIL"],
    "missed_must_cover": [],
    "reference_comparison": None,
    "review": [REVIEW],
}
DETAIL = {
    "focus": FOCUS,
    "skill": "Python",
    "required": True,
    "weight": 30,
    "expected_level": "mid",
    "reference_answer": None,
    "timeline": [
        {
            "question_seq": 2,
            "question_text": "Q?",
            "answer_seq": 3,
            "answer_text": "A GIL answer",
            "custom_question": False,
            "evidence": EVIDENCE,
        }
    ],
}


def test_focus_detail_serializes_to_the_wire_format() -> None:
    dumped = FocusDetail.model_validate(DETAIL).model_dump(mode="json")

    expected_review = REVIEW | {"created_at": "2026-11-02T10:00:00Z"}
    assert dumped["focus"] == FOCUS | {"review": [expected_review], "final_verdict": "weak"}
    assert dumped["timeline"] == DETAIL["timeline"]
    assert set(dumped) == set(DETAIL)


def test_final_verdict_falls_back_to_the_generated_verdict() -> None:
    payload = DETAIL | {"focus": FOCUS | {"review": []}}

    assert FocusDetail.model_validate(payload).focus.final_verdict == "strong"


@pytest.mark.parametrize("quote", [{"start": 4, "end": 4, "text": "G"}, {"start": 4, "end": 9, "text": "GIL"}])
def test_quote_span_must_match_text(quote: dict) -> None:
    evidence = EVIDENCE | {"quotes": [EVIDENCE["quotes"][0] | quote]}

    with pytest.raises(ValidationError):
        FocusDetail.model_validate(DETAIL | {"timeline": [DETAIL["timeline"][0] | {"evidence": evidence}]})


def test_answer_must_follow_question() -> None:
    evidence = EVIDENCE | {"answer_seq": 2}

    with pytest.raises(ValidationError):
        FocusDetail.model_validate(DETAIL | {"timeline": [DETAIL["timeline"][0] | {"evidence": evidence}]})
