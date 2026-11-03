from datetime import timedelta
from uuid import uuid4

import pytest
from shared_models.assessment import (
    AssessmentContext,
    CandidateMessage,
    CvPolicy,
    InterviewerMessage,
    SessionCompleted,
    SessionPaused,
    fold_events,
)
from shared_models.assessment.mocks import mock_assessment_context
from shared_models.assessment.session_events import CompletionReason, MessageKind
from shared_models.assessment.session_state import SessionStatus
from shared_models.cv.cv_data import CVData
from src.application.services.interview_turn_service import MessageDelta
from src.domain.entities.interview_connection import InterviewConnection
from src.domain.exceptions.assessment_context_errors import AssessmentNotReadyError
from src.domain.exceptions.session_errors import NoPendingQuestionError, SessionBusyError, SessionCompletedError
from src.domain.interview.dto import EvaluationResult

from tests.unit_tests.fakes import FIXED_NOW, FakeStack, ScriptedEvaluator


class Harness:
    def __init__(
        self,
        policy: CvPolicy = CvPolicy.REQUIRED,
        cv: CVData | None = CVData(),
        evaluator: ScriptedEvaluator | None = None,
    ) -> None:
        self.context: AssessmentContext = mock_assessment_context(policy)
        self.connection = InterviewConnection(attempt_id=self.context.attempt_id, context=self.context)
        self.stack = FakeStack(context=self.context, cv=cv, evaluator=evaluator)
        self.container = self.stack.container
        self.journal = self.stack.event_repository
        self.lock = self.stack.lock
        self.evaluator = self.stack.evaluator
        self.interviewer = self.stack.interviewer
        self.cv_provider = self.stack.cv_repository
        self.publisher = self.stack.publisher
        self.outbox = self.stack.completion_outbox_repository
        self.presence = self.stack.presence

    @property
    def now(self):
        return self.stack.now

    @now.setter
    def now(self, value) -> None:
        self.stack.now = value

    @property
    def session_id(self) -> str:
        return str(self.connection.attempt_id)

    async def open(self) -> list:
        return [output async for output in self.container.open_interview_session_use_case(self.connection)]

    async def answer(self, text: str = "I would profile the query first", turn_id=None) -> list:
        turn_id = turn_id or uuid4()
        return [
            output async for output in self.container.handle_candidate_answer_use_case(self.connection, turn_id, text)
        ]

    async def state(self):
        return fold_events(self.journal.events[self.session_id])


async def test_first_open_starts_session_and_streams_the_first_question() -> None:
    harness = Harness()

    outputs = await harness.open()

    deltas = [o for o in outputs if isinstance(o, MessageDelta)]
    message = outputs[-1]
    assert "".join(d.delta for d in deltas) == message.text
    assert isinstance(message, InterviewerMessage)
    assert (message.kind, message.focus_id, message.custom_question_index) == (MessageKind.QUESTION, "databases", 0)
    state = await harness.state()
    assert state.cv_attached is True
    assert set(harness.cv_provider.requested) == {harness.context.cv_correlation_id}


async def test_open_is_idempotent_while_a_question_is_pending() -> None:
    harness = Harness()
    await harness.open()

    assert await harness.open() == []
    assert len(harness.interviewer.requests) == 1


async def test_no_cv_policy_starts_with_an_uncounted_intro() -> None:
    harness = Harness(CvPolicy.NONE, cv=None)

    intro = (await harness.open())[-1]
    await harness.answer("I have three years of Python experience")

    state = await harness.state()
    assert intro.kind == MessageKind.INTRO
    assert harness.evaluator.requests == []
    assert state.cv_attached is False
    assert state.questions_asked == 1
    assert state.evidence == []


async def test_required_cv_that_is_missing_blocks_the_session() -> None:
    harness = Harness(CvPolicy.REQUIRED, cv=None)

    with pytest.raises(AssessmentNotReadyError):
        await harness.open()
    assert harness.journal.events == {}


async def test_answer_is_evaluated_and_evidence_and_coverage_are_journaled() -> None:
    harness = Harness()
    await harness.open()

    outputs = await harness.answer("First I would run EXPLAIN ANALYZE on the query")

    state = await harness.state()
    assert outputs[-1].kind in (MessageKind.QUESTION, MessageKind.FOLLOW_UP)
    assert harness.evaluator.requests[0].target_focus.id == "databases"
    assert len(state.evidence) == 1
    assert state.evidence[0].quotes[0].text == "First I woul"
    assert state.coverage["databases"].evidence_count == 1
    assert state.coverage["databases"].covered_must_cover == ["indexes"]


async def test_quote_that_is_not_in_the_answer_is_dropped() -> None:
    evaluator = ScriptedEvaluator(
        lambda request: EvaluationResult(
            answer_was_complete=True,
            evidence=[
                {
                    "focus_id": request.target_focus.id,
                    "level": "strong",
                    "quotes": ["text the candidate never wrote"],
                    "reasoning": "Hallucinated quote.",
                }
            ],
        )
    )
    harness = Harness(evaluator=evaluator)
    await harness.open()

    await harness.answer("a short answer")

    state = await harness.state()
    assert state.evidence == []
    assert state.coverage["databases"].evidence_count == 0


async def test_evaluator_failure_does_not_lose_the_turn() -> None:
    harness = Harness()
    harness.evaluator.fail = True
    await harness.open()

    outputs = await harness.answer()

    assert isinstance(outputs[-1], InterviewerMessage)
    assert (await harness.state()).evidence == []


async def test_repeated_turn_id_replays_the_reply_without_a_new_evaluation() -> None:
    harness = Harness()
    await harness.open()
    turn_id = uuid4()
    first = await harness.answer("an answer", turn_id)

    replay = await harness.answer("an answer", turn_id)

    assert replay == [first[-1]]
    assert len(harness.evaluator.requests) == 1
    assert len([e for e in harness.journal.events[harness.session_id] if isinstance(e, CandidateMessage)]) == 1


async def test_answer_stored_before_a_crash_is_continued() -> None:
    harness = Harness()
    await harness.open()
    turn_id = uuid4()
    state = await harness.state()
    await harness.journal.append(
        CandidateMessage(
            event_id=uuid4(),
            session_id=harness.session_id,
            seq=state.last_seq + 1,
            occurred_at=FIXED_NOW,
            turn_id=turn_id,
            text="answer written before the crash",
        )
    )

    outputs = await harness.answer("answer written before the crash", turn_id)

    assert isinstance(outputs[-1], InterviewerMessage)
    assert len(harness.evaluator.requests) == 1


async def test_answer_before_the_session_starts_is_rejected() -> None:
    harness = Harness()

    with pytest.raises(NoPendingQuestionError):
        await harness.answer()


async def test_second_answer_to_the_same_question_is_rejected() -> None:
    harness = Harness()
    await harness.open()
    harness.interviewer.empty = True
    harness.context.template.custom_questions.clear()

    with pytest.raises(ValueError):
        await harness.answer("first answer")
    with pytest.raises(NoPendingQuestionError):
        await harness.answer("second answer")


async def test_busy_session_rejects_the_turn() -> None:
    harness = Harness()
    await harness.open()
    harness.lock.held.add(harness.session_id)

    with pytest.raises(SessionBusyError):
        await harness.answer()


async def run_to_completion(harness: Harness) -> list:
    outputs = await harness.open()
    for _ in range(40):
        if isinstance(outputs[-1], SessionCompleted):
            return outputs
        outputs = await harness.answer("a considered answer about the topic")
    raise AssertionError("interview did not complete")


async def test_interview_runs_to_completion_and_publishes_the_event() -> None:
    harness = Harness()

    outputs = await run_to_completion(harness)

    state = await harness.state()
    assert state.status == SessionStatus.COMPLETED
    assert state.completion_reason == CompletionReason.QUESTION_BUDGET
    assert state.questions_asked == harness.context.template.question_count
    assert isinstance(outputs[-2], InterviewerMessage) and outputs[-2].kind == MessageKind.CLOSING

    [event] = harness.publisher.events
    assert event.attempt_id == harness.context.attempt_id
    assert event.session_id == harness.session_id
    assert event.report_reference.startswith("interview-report:")
    assert event.organization_id == harness.context.organization_id
    dumped = event.model_dump_json()
    assert "Alex Candidate" not in dumped and "a considered answer" not in dumped


async def test_completed_session_rejects_answers_and_republishes_idempotently_on_open() -> None:
    harness = Harness()
    await run_to_completion(harness)

    with pytest.raises(SessionCompletedError):
        await harness.answer()
    assert await harness.open() == []

    assert len(harness.publisher.events) == 2
    assert harness.publisher.events[0].event_id == harness.publisher.events[1].event_id


async def test_publish_failure_does_not_fail_the_completed_interview() -> None:
    harness = Harness()
    harness.publisher.fail = True

    await run_to_completion(harness)

    assert (await harness.state()).status == SessionStatus.COMPLETED


async def test_time_budget_ends_the_interview() -> None:
    harness = Harness()
    await harness.open()
    harness.now += timedelta(minutes=harness.context.template.duration_minutes + 1)

    outputs = await harness.answer()

    assert isinstance(outputs[-1], SessionCompleted)
    assert outputs[-1].reason == CompletionReason.TIME_BUDGET


async def test_disconnect_pauses_only_a_running_session() -> None:
    harness = Harness()
    token = await harness.container.register_interview_connection_use_case(harness.connection)
    await harness.container.pause_interview_session_use_case(harness.connection, token)
    assert harness.journal.events == {}

    token = await harness.container.register_interview_connection_use_case(harness.connection)
    await harness.open()
    await harness.container.pause_interview_session_use_case(harness.connection, token)
    await harness.container.pause_interview_session_use_case(harness.connection, token)

    events = harness.journal.events[harness.session_id]
    assert len([e for e in events if isinstance(e, SessionPaused)]) == 1
    assert (await harness.state()).status == SessionStatus.PAUSED


async def test_a_superseded_connection_does_not_pause_the_resumed_session() -> None:
    harness = Harness()
    old_token = await harness.container.register_interview_connection_use_case(harness.connection)
    await harness.open()
    new_token = await harness.container.register_interview_connection_use_case(harness.connection)

    await harness.container.pause_interview_session_use_case(harness.connection, old_token)

    assert (await harness.state()).status == SessionStatus.IN_PROGRESS
    await harness.container.pause_interview_session_use_case(harness.connection, new_token)
    assert (await harness.state()).status == SessionStatus.PAUSED


async def test_resumed_session_continues_after_a_pause() -> None:
    harness = Harness()
    token = await harness.container.register_interview_connection_use_case(harness.connection)
    await harness.open()
    await harness.container.pause_interview_session_use_case(harness.connection, token)

    outputs = await harness.answer("answer after reconnecting")

    assert isinstance(outputs[-1], InterviewerMessage)
    assert (await harness.state()).status == SessionStatus.IN_PROGRESS


async def test_time_spent_disconnected_does_not_use_up_the_time_budget() -> None:
    harness = Harness()
    token = await harness.container.register_interview_connection_use_case(harness.connection)
    await harness.open()
    harness.now += timedelta(minutes=5)
    await harness.container.pause_interview_session_use_case(harness.connection, token)
    harness.now += timedelta(minutes=harness.context.template.duration_minutes + 10)

    outputs = await harness.answer("back after a long break")

    assert isinstance(outputs[-1], InterviewerMessage) and outputs[-1].kind != MessageKind.CLOSING


async def test_completion_is_stored_durably_before_publishing_and_survives_a_broker_outage() -> None:
    harness = Harness()
    harness.publisher.fail = True

    await run_to_completion(harness)

    [event] = harness.outbox.list_pending.__self__.events.values()
    assert harness.outbox.published == set() and harness.publisher.events == []
    assert [e.event_id for e in await harness.outbox.list_pending(10)] == [event.event_id]


async def test_the_dispatcher_publishes_pending_completions_once_the_broker_recovers() -> None:
    from src.infrastructure.rabbitmq.completion_outbox_dispatcher import CompletionOutboxDispatcher

    harness = Harness()
    harness.publisher.fail = True
    await run_to_completion(harness)
    dispatcher = CompletionOutboxDispatcher(harness.outbox, harness.publisher)

    assert await dispatcher.dispatch_once() == 0
    harness.publisher.fail = False
    assert await dispatcher.dispatch_once() == 1
    assert await dispatcher.dispatch_once() == 0
    assert len(harness.publisher.events) == 1 and await harness.outbox.list_pending(10) == []


async def test_a_published_completion_is_marked_and_not_retried() -> None:
    harness = Harness()

    await run_to_completion(harness)

    assert len(harness.outbox.published) == 1 and await harness.outbox.list_pending(10) == []


async def test_the_cv_is_fetched_once_per_session_service() -> None:
    harness = Harness()
    await harness.open()
    await harness.answer("first answer")
    await harness.answer("second answer")

    assert len(harness.cv_provider.requested) == 1
