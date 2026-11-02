from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4, uuid5

from shared_models.assessment import (
    AssessmentCompleted,
    CandidateMessage,
    CvPolicy,
    EvidenceRecorded,
    FocusCoverageChanged,
    InterviewerMessage,
    SessionCompleted,
    SessionEvent,
    SessionPaused,
    SessionStarted,
    fold_events,
)
from shared_models.assessment.session_events import MessageKind, PauseReason
from shared_models.assessment.session_state import SessionState, SessionStatus
from shared_models.cv.cv_data import CVData

from src.domain.entities.interview_connection import InterviewConnection
from src.domain.exceptions.assessment_context_errors import AssessmentNotReadyError
from src.domain.exceptions.session_errors import NoPendingQuestionError, SessionCompletedError
from src.domain.interfaces.answer_evaluator import IAnswerEvaluator
from src.domain.interfaces.assessment_completed_publisher import IAssessmentCompletedPublisher
from src.domain.interfaces.candidate_cv_provider import ICandidateCvProvider
from src.domain.interfaces.completion_outbox import ICompletionOutbox
from src.domain.interfaces.event_journal import IEventJournal
from src.domain.interfaces.interviewer_agent import IInterviewerAgent
from src.domain.interfaces.session_lock import ISessionLock
from src.domain.interfaces.session_presence import ISessionPresence
from src.domain.interview.dto import EvaluationRequest, EvaluationResult, InterviewerRequest
from src.domain.interview.engine import ASKING_KINDS, AskFocus, AskIntro, Complete, InterviewEngine, NextAction
from src.domain.interview.evidence import build_evidence_items
from src.logger import app_logger

COMPLETION_NAMESPACE = UUID("8d7b6c5e-3f2a-4e1b-a9c0-4b5d6e7f8a90")
TRANSCRIPT_TAIL = 8
CV_CACHE_SIZE = 256


@dataclass(frozen=True)
class MessageDelta:
    turn_id: UUID
    message_id: UUID
    delta: str


SessionOutput = MessageDelta | InterviewerMessage | SessionCompleted


class InterviewSessionService:
    def __init__(
        self,
        journal: IEventJournal,
        lock: ISessionLock,
        evaluator: IAnswerEvaluator,
        interviewer: IInterviewerAgent,
        cv_provider: ICandidateCvProvider,
        completed_publisher: IAssessmentCompletedPublisher,
        completion_outbox: ICompletionOutbox,
        presence: ISessionPresence,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._journal = journal
        self._lock = lock
        self._evaluator = evaluator
        self._interviewer = interviewer
        self._cv_provider = cv_provider
        self._completed_publisher = completed_publisher
        self._completion_outbox = completion_outbox
        self._presence = presence
        self._clock = clock
        self._cv_cache: dict[UUID, CVData] = {}

    async def list_events(self, connection: InterviewConnection) -> list[SessionEvent]:
        return await self._journal.list_events(str(connection.attempt_id))

    async def open_session(self, connection: InterviewConnection) -> AsyncIterator[SessionOutput]:
        session_id = str(connection.attempt_id)
        async with self._lock.hold(session_id):
            events = await self._journal.list_events(session_id)
            if not events:
                events = [await self._start_session(connection, session_id)]
            state = fold_events(events)
            if state.status == SessionStatus.COMPLETED:
                await self._publish_completion(connection, session_id)
                return
            if InterviewEngine(connection.context.template).pending_question(state) is not None:
                return
            async for output in self._advance(connection, events, uuid4()):
                yield output

    async def handle_answer(
        self, connection: InterviewConnection, turn_id: UUID, text: str
    ) -> AsyncIterator[SessionOutput]:
        session_id = str(connection.attempt_id)
        async with self._lock.hold(session_id):
            events = await self._journal.list_events(session_id)
            if not events:
                raise NoPendingQuestionError()
            state = fold_events(events)
            if state.status == SessionStatus.COMPLETED:
                raise SessionCompletedError()

            existing = self._find_answer(events, turn_id)
            if existing is not None:
                replies = self._replies_to(events, existing)
                if replies:
                    for reply in replies:
                        yield reply
                    return
            else:
                if InterviewEngine(connection.context.template).pending_question(state) is None:
                    raise NoPendingQuestionError()
                existing = CandidateMessage(
                    event_id=uuid4(),
                    session_id=session_id,
                    seq=state.last_seq + 1,
                    occurred_at=self._clock(),
                    turn_id=turn_id,
                    text=text,
                )
                await self._journal.append(existing)
                events.append(existing)

            await self._record_evidence(connection, events, existing)
            async for output in self._advance(connection, events, turn_id):
                yield output

    async def register_connection(self, connection: InterviewConnection) -> str:
        return await self._presence.claim(str(connection.attempt_id))

    async def pause_session(self, connection: InterviewConnection, token: str) -> None:
        session_id = str(connection.attempt_id)
        if not await self._presence.release(session_id, token):
            return
        async with self._lock.hold(session_id):
            events = await self._journal.list_events(session_id)
            if not events or fold_events(events).status != SessionStatus.IN_PROGRESS:
                return
            await self._journal.append(
                SessionPaused(
                    event_id=uuid4(),
                    session_id=session_id,
                    seq=events[-1].seq + 1,
                    occurred_at=self._clock(),
                    reason=PauseReason.DISCONNECT,
                )
            )

    async def _start_session(self, connection: InterviewConnection, session_id: str) -> SessionStarted:
        context = connection.context
        cv = await self._load_cv(connection)
        started = SessionStarted(
            event_id=uuid4(),
            session_id=session_id,
            seq=1,
            occurred_at=self._clock(),
            attempt_id=connection.attempt_id,
            template_version=context.template_version,
            cv_attached=cv is not None,
        )
        await self._journal.append(started)
        return started

    async def _load_cv(self, connection: InterviewConnection) -> CVData | None:
        context = connection.context
        if context.cv_correlation_id is None:
            return None
        cached = self._cv_cache.get(context.cv_correlation_id)
        if cached is not None:
            return cached
        cv = await self._cv_provider.get(context.cv_correlation_id)
        if cv is None and context.cv_policy == CvPolicy.REQUIRED:
            raise AssessmentNotReadyError()
        if cv is not None:
            if len(self._cv_cache) >= CV_CACHE_SIZE:
                self._cv_cache.clear()
            self._cv_cache[context.cv_correlation_id] = cv
        return cv

    @staticmethod
    def _find_answer(events: list[SessionEvent], turn_id: UUID) -> CandidateMessage | None:
        return next((e for e in events if isinstance(e, CandidateMessage) and e.turn_id == turn_id), None)

    @staticmethod
    def _replies_to(
        events: list[SessionEvent], answer: CandidateMessage
    ) -> list[InterviewerMessage | SessionCompleted]:
        replies: list[InterviewerMessage | SessionCompleted] = []
        for event in events:
            if event.seq <= answer.seq:
                continue
            if isinstance(event, InterviewerMessage) and event.turn_id == answer.turn_id:
                replies.append(event)
            elif isinstance(event, SessionCompleted) and replies:
                replies.append(event)
        return replies

    async def _record_evidence(
        self, connection: InterviewConnection, events: list[SessionEvent], answer: CandidateMessage
    ) -> None:
        state = fold_events(events)
        if any(item.answer_seq == answer.seq for item in state.evidence):
            return
        question = next(
            (state.messages[seq] for seq in sorted(state.messages, reverse=True) if seq < answer.seq),
            None,
        )
        if question is None or question.role != "interviewer" or question.kind not in ASKING_KINDS:
            return

        template = connection.context.template
        engine = InterviewEngine(template)
        focus = template.focus_by_id(question.focus_id or "")
        try:
            result = await self._evaluator.evaluate(
                EvaluationRequest(
                    template=template, target_focus=focus, question_text=question.text, answer_text=answer.text
                )
            )
        except Exception:
            app_logger.exception("Answer evaluation failed for session %s", answer.session_id)
            result = EvaluationResult(answer_was_complete=False)

        items = build_evidence_items(
            result.evidence, template, answer.session_id, question.seq, answer.seq, answer.text
        )
        for item in items:
            event = EvidenceRecorded(
                event_id=uuid4(),
                session_id=answer.session_id,
                seq=events[-1].seq + 1,
                occurred_at=self._clock(),
                evidence=item,
            )
            await self._journal.append(event)
            events.append(event)

        state = fold_events(events)
        touched = [focus.id] + [item.focus_id for item in items if item.focus_id != focus.id]
        for focus_id in touched:
            topics = result.covered_must_cover if focus_id == focus.id else []
            status, count, covered = engine.coverage_after_answer(state, focus_id, topics)
            event = FocusCoverageChanged(
                event_id=uuid4(),
                session_id=answer.session_id,
                seq=events[-1].seq + 1,
                occurred_at=self._clock(),
                focus_id=focus_id,
                status=status,
                evidence_count=count,
                covered_must_cover=covered,
            )
            await self._journal.append(event)
            events.append(event)

    async def _advance(
        self, connection: InterviewConnection, events: list[SessionEvent], turn_id: UUID
    ) -> AsyncIterator[SessionOutput]:
        template = connection.context.template
        state = fold_events(events)
        action = InterviewEngine(template).next_action(state, state.active_elapsed(self._clock()))
        cv = await self._load_cv(connection) if state.cv_attached else None
        request = self._interviewer_request(connection, state, action, cv)

        message_id = uuid4()
        parts: list[str] = []
        async for delta in self._interviewer.stream_message(request):
            parts.append(delta)
            yield MessageDelta(turn_id=turn_id, message_id=message_id, delta=delta)
        text = "".join(parts).strip()
        if not text:
            text = self._fallback_text(request)

        message = InterviewerMessage(
            event_id=message_id,
            session_id=state.session_id,
            seq=events[-1].seq + 1,
            occurred_at=self._clock(),
            turn_id=turn_id,
            kind=self._message_kind(action),
            text=text,
            focus_id=action.focus_id if isinstance(action, AskFocus) else None,
            custom_question_index=action.custom_question_index if isinstance(action, AskFocus) else None,
        )
        await self._journal.append(message)
        events.append(message)
        yield message

        if isinstance(action, Complete):
            completed = SessionCompleted(
                event_id=uuid4(),
                session_id=state.session_id,
                seq=message.seq + 1,
                occurred_at=self._clock(),
                reason=action.reason,
            )
            await self._journal.append(completed)
            events.append(completed)
            yield completed
            await self._publish_completion(connection, state.session_id)

    @staticmethod
    def _message_kind(action: NextAction) -> MessageKind:
        if isinstance(action, AskIntro):
            return MessageKind.INTRO
        if isinstance(action, AskFocus):
            return action.kind
        return MessageKind.CLOSING

    @staticmethod
    def _fallback_text(request: InterviewerRequest) -> str:
        if request.custom_question is not None:
            return request.custom_question.text
        raise ValueError("Interviewer returned an empty message")

    @staticmethod
    def _interviewer_request(
        connection: InterviewConnection, state: SessionState, action: NextAction, cv: CVData | None
    ) -> InterviewerRequest:
        template = connection.context.template
        focus = template.focus_by_id(action.focus_id) if isinstance(action, AskFocus) else None
        custom = None
        if isinstance(action, AskFocus) and action.custom_question_index is not None:
            custom = template.custom_questions[action.custom_question_index]
        tail = [state.messages[seq] for seq in sorted(state.messages)][-TRANSCRIPT_TAIL:]
        return InterviewerRequest(
            template=template,
            action=action,
            focus=focus,
            custom_question=custom,
            coverage=state.coverage.get(focus.id) if focus else None,
            cv=cv,
            transcript=tail,
        )

    async def _publish_completion(self, connection: InterviewConnection, session_id: str) -> None:
        context = connection.context
        event = AssessmentCompleted(
            event_id=uuid5(COMPLETION_NAMESPACE, f"{session_id}/completed"),
            occurred_at=self._clock(),
            correlation_id=uuid5(COMPLETION_NAMESPACE, session_id),
            organization_id=context.organization_id,
            vacancy_id=context.vacancy_id,
            invitation_id=context.invitation_id,
            attempt_id=connection.attempt_id,
            session_id=session_id,
            report_reference=f"interview-report:{session_id}",
            report_version=1,
        )
        try:
            await self._completion_outbox.enqueue(event)
            await self._completed_publisher.publish(event)
            await self._completion_outbox.mark_published(event.event_id)
        except Exception:
            app_logger.exception("Publishing AssessmentCompleted failed for session %s", session_id)
