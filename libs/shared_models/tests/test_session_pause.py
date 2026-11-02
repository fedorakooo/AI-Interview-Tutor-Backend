from datetime import timedelta
from uuid import uuid4

from shared_models.assessment import CandidateMessage, SessionPaused, fold_events
from shared_models.assessment.mocks import mock_session_events
from shared_models.assessment.session_events import PauseReason
from shared_models.assessment.session_state import SessionStatus

SESSION_START = mock_session_events()[0].occurred_at


def prefix(count: int) -> list:
    return list(mock_session_events()[:count])


def pause_after(events: list, minutes: int) -> SessionPaused:
    return SessionPaused(
        event_id=uuid4(),
        session_id=events[0].session_id,
        seq=events[-1].seq + 1,
        occurred_at=SESSION_START + timedelta(minutes=minutes),
        reason=PauseReason.DISCONNECT,
    )


def answer_after(events: list, minutes: int) -> CandidateMessage:
    return CandidateMessage(
        event_id=uuid4(),
        session_id=events[0].session_id,
        seq=events[-1].seq + 1,
        occurred_at=SESSION_START + timedelta(minutes=minutes),
        turn_id=uuid4(),
        text="answer after reconnecting",
    )


def test_time_spent_paused_is_excluded_after_the_session_resumes() -> None:
    events = prefix(2)
    events.append(pause_after(events, 5))
    events.append(answer_after(events, 55))

    state = fold_events(events)

    assert state.status == SessionStatus.IN_PROGRESS
    assert state.active_elapsed(SESSION_START + timedelta(minutes=60)) == timedelta(minutes=10)


def test_an_open_pause_is_excluded_up_to_now() -> None:
    events = prefix(2)
    events.append(pause_after(events, 5))

    state = fold_events(events)

    assert state.status == SessionStatus.PAUSED
    assert state.active_elapsed(SESSION_START + timedelta(minutes=90)) == timedelta(minutes=5)


def test_multiple_pauses_accumulate() -> None:
    events = prefix(2)
    events.append(pause_after(events, 2))
    events.append(answer_after(events, 12))
    events.append(pause_after(events, 14))
    events.append(answer_after(events, 24))

    assert fold_events(events).active_elapsed(SESSION_START + timedelta(minutes=30)) == timedelta(minutes=10)


def test_a_session_without_pauses_uses_wall_clock_time() -> None:
    state = fold_events(prefix(3))

    assert state.active_elapsed(SESSION_START + timedelta(minutes=7)) == timedelta(minutes=7)
