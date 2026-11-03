from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from shared_models.assessment import CandidateMessage, SessionEvent, SessionPaused, fold_events
from shared_models.assessment.session_events import PauseReason
from shared_models.assessment.session_state import SessionStatus

from src.application.services.interview_turn_service import InterviewTurnService, SessionOutput
from src.domain.entities.interview_connection import InterviewConnection
from src.domain.exceptions.session_errors import NoPendingQuestionError, SessionCompletedError
from src.domain.interfaces.interview_event_repository import IInterviewEventRepository
from src.domain.interfaces.session_lock import ISessionLock
from src.domain.interfaces.session_presence import ISessionPresence
from src.domain.interview.engine import InterviewEngine


class ListInterviewEventsUseCase:
    def __init__(self, event_repository: IInterviewEventRepository):
        self._event_repository = event_repository

    async def __call__(self, connection: InterviewConnection) -> list[SessionEvent]:
        return await self._event_repository.list_events(str(connection.attempt_id))


class RegisterInterviewConnectionUseCase:
    def __init__(self, presence: ISessionPresence):
        self._presence = presence

    async def __call__(self, connection: InterviewConnection) -> str:
        return await self._presence.claim(str(connection.attempt_id))


class OpenInterviewSessionUseCase:
    def __init__(
        self, lock: ISessionLock, event_repository: IInterviewEventRepository, turn_service: InterviewTurnService
    ):
        self._lock = lock
        self._event_repository = event_repository
        self._turns = turn_service

    async def __call__(self, connection: InterviewConnection) -> AsyncIterator[SessionOutput]:
        session_id = str(connection.attempt_id)
        async with self._lock.hold(session_id):
            events = await self._event_repository.list_events(session_id)
            if not events:
                events = [await self._turns.start_session(connection, session_id)]
            state = fold_events(events)
            if state.status == SessionStatus.COMPLETED:
                await self._turns.publish_completion(connection, session_id)
                return
            if InterviewEngine(connection.context.template).pending_question(state) is not None:
                return
            turn_id = uuid4()
            last_message_seq = max(state.messages, default=None)
            if last_message_seq is not None and state.messages[last_message_seq].role == "candidate":
                answer = next(
                    e for e in reversed(events) if isinstance(e, CandidateMessage) and e.seq == last_message_seq
                )
                await self._turns.record_evidence(connection, events, answer)
                turn_id = answer.turn_id
            async for output in self._turns.advance(connection, events, turn_id):
                yield output


class HandleCandidateAnswerUseCase:
    def __init__(
        self,
        lock: ISessionLock,
        event_repository: IInterviewEventRepository,
        turn_service: InterviewTurnService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._lock = lock
        self._event_repository = event_repository
        self._turns = turn_service
        self._clock = clock

    async def __call__(self, connection: InterviewConnection, turn_id: UUID, text: str) -> AsyncIterator[SessionOutput]:
        session_id = str(connection.attempt_id)
        async with self._lock.hold(session_id):
            events = await self._event_repository.list_events(session_id)
            if not events:
                raise NoPendingQuestionError()
            state = fold_events(events)
            if state.status == SessionStatus.COMPLETED:
                raise SessionCompletedError()

            existing = self._turns.find_answer(events, turn_id)
            if existing is not None:
                replies = self._turns.replies_to(events, existing)
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
                await self._event_repository.append(existing)
                events.append(existing)

            await self._turns.record_evidence(connection, events, existing)
            async for output in self._turns.advance(connection, events, turn_id):
                yield output


class PauseInterviewSessionUseCase:
    def __init__(
        self,
        lock: ISessionLock,
        presence: ISessionPresence,
        event_repository: IInterviewEventRepository,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._lock = lock
        self._presence = presence
        self._event_repository = event_repository
        self._clock = clock

    async def __call__(self, connection: InterviewConnection, token: str) -> None:
        session_id = str(connection.attempt_id)
        if not await self._presence.release(session_id, token):
            return
        async with self._lock.hold(session_id):
            events = await self._event_repository.list_events(session_id)
            if not events or fold_events(events).status != SessionStatus.IN_PROGRESS:
                return
            await self._event_repository.append(
                SessionPaused(
                    event_id=uuid4(),
                    session_id=session_id,
                    seq=events[-1].seq + 1,
                    occurred_at=self._clock(),
                    reason=PauseReason.DISCONNECT,
                )
            )
