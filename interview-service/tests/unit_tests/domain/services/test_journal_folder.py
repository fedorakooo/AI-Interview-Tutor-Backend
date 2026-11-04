from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest
from src.domain.enums.completion_reason import CompletionReason
from src.domain.enums.cv_policy import CvPolicy
from src.domain.enums.message_kind import MessageKind
from src.domain.enums.pause_reason import PauseReason
from src.domain.enums.session_status import SessionStatus
from src.domain.events.candidate_message import CandidateMessage
from src.domain.events.session_event import SessionEvent
from src.domain.events.session_paused import SessionPaused
from src.domain.exceptions.session_errors import InconsistentJournalError
from src.domain.services.journal_folder import JournalFolder

from tests.fakes.builders import build_events, build_template

POLICIES = [CvPolicy.REQUIRED, CvPolicy.NONE]
SESSION_START = build_events()[0].occurred_at


def prefix(count: int) -> list[SessionEvent]:
    return build_events()[:count]


def pause_after(events: list[SessionEvent], minutes: int) -> SessionPaused:
    return SessionPaused(
        event_id=uuid4(),
        session_id=events[0].session_id,
        seq=events[-1].seq + 1,
        occurred_at=SESSION_START + timedelta(minutes=minutes),
        reason=PauseReason.DISCONNECT,
    )


def answer_after(events: list[SessionEvent], minutes: int) -> CandidateMessage:
    return CandidateMessage(
        event_id=uuid4(),
        session_id=events[0].session_id,
        seq=events[-1].seq + 1,
        occurred_at=SESSION_START + timedelta(minutes=minutes),
        turn_id=uuid4(),
        text="answer after reconnecting",
    )


@pytest.mark.parametrize("policy", POLICIES)
class TestFold:
    def test_fold_of_a_completed_mock_session(self, policy: CvPolicy) -> None:
        state = JournalFolder.fold(build_events(policy))

        assert state.status == SessionStatus.COMPLETED
        assert state.completion_reason == CompletionReason.QUESTION_BUDGET
        assert state.questions_asked == build_template(policy).question_count
        assert state.cv_attached is (policy != CvPolicy.NONE)
        assert len(state.evidence) == 9
        assert state.coverage["testing"].evidence_count == 1

    def test_seq_is_monotonic(self, policy: CvPolicy) -> None:
        seqs = [event.seq for event in build_events(policy)]

        assert seqs == sorted(set(seqs))

    def test_intro_turn_is_not_counted_and_not_evidence(self, policy: CvPolicy) -> None:
        state = JournalFolder.fold(build_events(policy))
        intro = [message for message in state.messages.values() if message.kind == MessageKind.INTRO]

        assert len(intro) == (1 if policy == CvPolicy.NONE else 0)
        assert all(item.question_seq not in {message.seq for message in intro} for item in state.evidence)

    def test_rejects_events_after_a_terminal_event(self, policy: CvPolicy) -> None:
        events = build_events(policy)
        late = replace(events[-1], seq=events[-1].seq + 1, event_id=uuid4())

        with pytest.raises(InconsistentJournalError, match="terminal"):
            JournalFolder.fold([*events, late])

    def test_rejects_a_non_monotonic_seq(self, policy: CvPolicy) -> None:
        events = build_events(policy)
        events[3] = replace(events[3], seq=events[2].seq)

        with pytest.raises(InconsistentJournalError, match="monotonically"):
            JournalFolder.fold(events)

    def test_rejects_a_log_that_does_not_start_with_session_started(self, policy: CvPolicy) -> None:
        with pytest.raises(InconsistentJournalError, match="start with SessionStarted"):
            JournalFolder.fold(build_events(policy)[1:])

    def test_rejects_an_empty_log(self, policy: CvPolicy) -> None:
        with pytest.raises(InconsistentJournalError, match="empty"):
            JournalFolder.fold([])


class TestPauses:
    def test_time_spent_paused_is_excluded_after_the_session_resumes(self) -> None:
        events = prefix(2)
        events.append(pause_after(events, 5))
        events.append(answer_after(events, 55))

        state = JournalFolder.fold(events)

        assert state.status == SessionStatus.IN_PROGRESS
        assert state.active_elapsed(SESSION_START + timedelta(minutes=60)) == timedelta(minutes=10)

    def test_an_open_pause_is_excluded_up_to_now(self) -> None:
        events = prefix(2)
        events.append(pause_after(events, 5))

        state = JournalFolder.fold(events)

        assert state.status == SessionStatus.PAUSED
        assert state.active_elapsed(SESSION_START + timedelta(minutes=90)) == timedelta(minutes=5)

    def test_multiple_pauses_accumulate(self) -> None:
        events = prefix(2)
        events.append(pause_after(events, 2))
        events.append(answer_after(events, 12))
        events.append(pause_after(events, 14))
        events.append(answer_after(events, 24))

        state = JournalFolder.fold(events)

        assert state.active_elapsed(SESSION_START + timedelta(minutes=30)) == timedelta(minutes=10)

    def test_a_session_without_pauses_uses_wall_clock_time(self) -> None:
        state = JournalFolder.fold(prefix(3))

        assert state.active_elapsed(SESSION_START + timedelta(minutes=7)) == timedelta(minutes=7)
