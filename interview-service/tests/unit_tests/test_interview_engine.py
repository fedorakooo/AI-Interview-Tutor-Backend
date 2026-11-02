from datetime import timedelta

import pytest
from shared_models.assessment import CvPolicy, EvidenceRecorded, fold_events
from shared_models.assessment.mocks import mock_session_events, mock_template
from shared_models.assessment.session_events import CompletionReason, CoverageStatus, FocusCoverageChanged, MessageKind
from shared_models.assessment.session_state import SessionState
from src.domain.interview.engine import AskFocus, AskIntro, Complete, InterviewEngine


def state_until(policy: CvPolicy, keep: int) -> SessionState:
    return fold_events(mock_session_events(policy)[:keep])


def test_engine_opens_with_intro_when_no_cv() -> None:
    engine = InterviewEngine(mock_template(CvPolicy.NONE))

    assert engine.next_action(state_until(CvPolicy.NONE, 1), timedelta()) == AskIntro()


def test_intro_is_asked_only_once() -> None:
    engine = InterviewEngine(mock_template(CvPolicy.NONE))

    action = engine.next_action(state_until(CvPolicy.NONE, 3), timedelta())

    assert isinstance(action, AskFocus)


def test_required_custom_question_goes_first() -> None:
    engine = InterviewEngine(mock_template(CvPolicy.REQUIRED))

    action = engine.next_action(state_until(CvPolicy.REQUIRED, 1), timedelta())

    assert action == AskFocus("databases", MessageKind.QUESTION, custom_question_index=0)


def test_pending_required_custom_question_outranks_other_focus_areas() -> None:
    template = mock_template(CvPolicy.REQUIRED)
    events = mock_session_events(CvPolicy.REQUIRED)
    after_first_exchange = next(i for i, e in enumerate(events) if isinstance(e, FocusCoverageChanged)) + 1

    action = InterviewEngine(template).next_action(fold_events(events[:after_first_exchange]), timedelta())

    assert action == AskFocus("databases", MessageKind.QUESTION, custom_question_index=0)


def coverage_complete_index(events: list) -> int:
    return max(i for i, event in enumerate(events) if isinstance(event, FocusCoverageChanged)) + 1


def test_question_budget_completes_the_interview() -> None:
    events = mock_session_events(CvPolicy.REQUIRED)
    state = fold_events(events[: coverage_complete_index(events)])

    action = InterviewEngine(mock_template(CvPolicy.REQUIRED)).next_action(state, timedelta())

    assert action == Complete(CompletionReason.QUESTION_BUDGET)


def test_time_budget_completes_the_interview() -> None:
    template = mock_template(CvPolicy.REQUIRED)

    action = InterviewEngine(template).next_action(
        state_until(CvPolicy.REQUIRED, 1), timedelta(minutes=template.duration_minutes)
    )

    assert action == Complete(CompletionReason.TIME_BUDGET)


def test_unfinished_focus_is_continued_while_budget_remains() -> None:
    template = mock_template(CvPolicy.REQUIRED).model_copy(update={"question_count": 30})
    events = mock_session_events(CvPolicy.REQUIRED)
    state = fold_events(events[: coverage_complete_index(events)])

    action = InterviewEngine(template).next_action(state, timedelta())

    assert action == AskFocus("testing", MessageKind.FOLLOW_UP)


def test_all_covered_completes_before_the_budget() -> None:
    template = mock_template(CvPolicy.REQUIRED)
    criteria = [
        focus.model_copy(update={"max_questions": 1}) if focus.id == "testing" else focus for focus in template.criteria
    ]
    template = template.model_copy(update={"question_count": 30, "criteria": criteria})
    events = mock_session_events(CvPolicy.REQUIRED)
    state = fold_events(events[: coverage_complete_index(events)])

    assert InterviewEngine(template).next_action(state, timedelta()) == Complete(CompletionReason.ALL_COVERED)


@pytest.mark.parametrize(
    ("evidence_total", "asked", "expected"),
    [
        (2, 2, CoverageStatus.COVERED),
        (1, 3, CoverageStatus.EXHAUSTED),
        (1, 1, CoverageStatus.IN_PROGRESS),
    ],
)
def test_coverage_status_after_answer(evidence_total: int, asked: int, expected: CoverageStatus) -> None:
    template = mock_template(CvPolicy.REQUIRED)
    events = mock_session_events(CvPolicy.REQUIRED)
    state = fold_events(events[: coverage_complete_index(events)])
    state.evidence = [
        e.evidence for e in events if isinstance(e, EvidenceRecorded) and e.evidence.focus_id == "databases"
    ][:evidence_total]
    engine = InterviewEngine(template)
    engine.questions_asked_for = lambda focus_id, _state: asked  # type: ignore[method-assign]

    status, count, covered = engine.coverage_after_answer(state, "databases", ["indexes", "unknown topic"])

    assert (status, count) == (expected, evidence_total)
    assert "unknown topic" not in covered
    assert "indexes" in covered


def test_pending_question_detection() -> None:
    engine = InterviewEngine(mock_template(CvPolicy.REQUIRED))
    events = mock_session_events(CvPolicy.REQUIRED)

    assert engine.pending_question(fold_events(events[:2])) is not None
    assert engine.pending_question(fold_events(events[:3])) is None
    assert engine.pending_question(fold_events(events)) is None
