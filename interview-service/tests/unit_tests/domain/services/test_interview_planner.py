from dataclasses import replace
from datetime import timedelta

import pytest
from src.domain.entities.session_state import SessionState
from src.domain.enums.completion_reason import CompletionReason
from src.domain.enums.coverage_status import CoverageStatus
from src.domain.enums.cv_policy import CvPolicy
from src.domain.enums.message_kind import MessageKind
from src.domain.events.evidence_recorded import EvidenceRecorded
from src.domain.events.focus_coverage_changed import FocusCoverageChanged
from src.domain.services.interview_planner import InterviewPlanner
from src.domain.services.journal_folder import JournalFolder
from src.domain.value_objects.ask_focus import AskFocus
from src.domain.value_objects.ask_intro import AskIntro
from src.domain.value_objects.complete import Complete

from tests.fakes.builders import build_events, build_template


def state_until(policy: CvPolicy, keep: int) -> SessionState:
    return JournalFolder.fold(build_events(policy)[:keep])


def test_planner_opens_with_intro_when_no_cv() -> None:
    planner = InterviewPlanner(build_template(CvPolicy.NONE))

    assert planner.next_action(state_until(CvPolicy.NONE, 1), timedelta()) == AskIntro()


def test_intro_is_asked_only_once() -> None:
    planner = InterviewPlanner(build_template(CvPolicy.NONE))

    action = planner.next_action(state_until(CvPolicy.NONE, 3), timedelta())

    assert isinstance(action, AskFocus)


def test_required_custom_question_goes_first() -> None:
    planner = InterviewPlanner(build_template(CvPolicy.REQUIRED))

    action = planner.next_action(state_until(CvPolicy.REQUIRED, 1), timedelta())

    assert action == AskFocus("databases", MessageKind.QUESTION, custom_question_index=0)


def test_pending_required_custom_question_outranks_other_focus_areas() -> None:
    template = build_template(CvPolicy.REQUIRED)
    events = build_events(CvPolicy.REQUIRED)
    after_first_exchange = next(i for i, e in enumerate(events) if isinstance(e, FocusCoverageChanged)) + 1

    action = InterviewPlanner(template).next_action(JournalFolder.fold(events[:after_first_exchange]), timedelta())

    assert action == AskFocus("databases", MessageKind.QUESTION, custom_question_index=0)


def coverage_complete_index(events: list) -> int:
    return max(i for i, event in enumerate(events) if isinstance(event, FocusCoverageChanged)) + 1


def test_question_budget_completes_the_interview() -> None:
    events = build_events(CvPolicy.REQUIRED)
    state = JournalFolder.fold(events[: coverage_complete_index(events)])

    action = InterviewPlanner(build_template(CvPolicy.REQUIRED)).next_action(state, timedelta())

    assert action == Complete(CompletionReason.QUESTION_BUDGET)


def test_time_budget_completes_the_interview() -> None:
    template = build_template(CvPolicy.REQUIRED)

    action = InterviewPlanner(template).next_action(
        state_until(CvPolicy.REQUIRED, 1), timedelta(minutes=template.duration_minutes)
    )

    assert action == Complete(CompletionReason.TIME_BUDGET)


def test_unfinished_focus_is_continued_while_budget_remains() -> None:
    template = replace(build_template(CvPolicy.REQUIRED), question_count=30)
    events = build_events(CvPolicy.REQUIRED)
    state = JournalFolder.fold(events[: coverage_complete_index(events)])

    action = InterviewPlanner(template).next_action(state, timedelta())

    assert action == AskFocus("testing", MessageKind.FOLLOW_UP)


def test_all_covered_completes_before_the_budget() -> None:
    template = build_template(CvPolicy.REQUIRED)
    criteria = tuple(
        replace(focus, max_questions=1, min_evidence=1) if focus.id == "testing" else focus
        for focus in template.criteria
    )
    template = replace(template, question_count=30, criteria=criteria)
    events = build_events(CvPolicy.REQUIRED)
    state = JournalFolder.fold(events[: coverage_complete_index(events)])

    assert InterviewPlanner(template).next_action(state, timedelta()) == Complete(CompletionReason.ALL_COVERED)


@pytest.mark.parametrize(
    ("evidence_total", "asked", "expected"),
    [
        (2, 2, CoverageStatus.COVERED),
        (1, 3, CoverageStatus.EXHAUSTED),
        (1, 1, CoverageStatus.IN_PROGRESS),
    ],
)
def test_coverage_status_after_answer(evidence_total: int, asked: int, expected: CoverageStatus) -> None:
    template = build_template(CvPolicy.REQUIRED)
    events = build_events(CvPolicy.REQUIRED)
    state = JournalFolder.fold(events[: coverage_complete_index(events)])
    state.evidence = [
        e.evidence for e in events if isinstance(e, EvidenceRecorded) and e.evidence.focus_id == "databases"
    ][:evidence_total]
    planner = InterviewPlanner(template)
    planner.questions_asked_for = lambda focus_id, _state: asked  # type: ignore[method-assign]

    status, count, covered = planner.coverage_after_answer(state, "databases", ("indexes", "unknown topic"))

    assert (status, count) == (expected, evidence_total)
    assert "unknown topic" not in covered
    assert "indexes" in covered


def test_pending_question_detection() -> None:
    planner = InterviewPlanner(build_template(CvPolicy.REQUIRED))
    events = build_events(CvPolicy.REQUIRED)

    assert planner.pending_question(JournalFolder.fold(events[:2])) is not None
    assert planner.pending_question(JournalFolder.fold(events[:3])) is None
    assert planner.pending_question(JournalFolder.fold(events)) is None
