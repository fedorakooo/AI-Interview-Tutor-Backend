from collections.abc import AsyncIterator, Callable
from datetime import datetime
from uuid import UUID, uuid4

from src.application.dtos.session_finished import SessionFinished
from src.application.dtos.session_output import SessionOutput
from src.application.dtos.transcript_entry import TranscriptEntry
from src.application.interfaces.interview_session_service import IInterviewSessionService
from src.application.mappers.session_output_mapper import SessionOutputMapper
from src.application.services.completion_publisher import CompletionPublisher
from src.application.services.cv_loader import CvLoader
from src.application.services.evidence_recorder import EvidenceRecorder
from src.application.services.interviewer_turn import InterviewerTurn
from src.domain.entities.interview_connection import InterviewConnection
from src.domain.enums.pause_reason import PauseReason
from src.domain.enums.session_status import SessionStatus
from src.domain.events.candidate_message import CandidateMessage
from src.domain.events.interviewer_message import InterviewerMessage
from src.domain.events.session_completed import SessionCompleted
from src.domain.events.session_event import SessionEvent
from src.domain.events.session_paused import SessionPaused
from src.domain.events.session_started import SessionStarted
from src.domain.exceptions.assessment_context_errors import AssessmentContextUnavailableError
from src.domain.exceptions.session_errors import NoPendingQuestionError, SessionCompletedError
from src.domain.interfaces.clients.assessment_context_client import IAssessmentContextClient
from src.domain.interfaces.clients.attempt_token_verifier import IAttemptTokenVerifier
from src.domain.interfaces.repositories.interview_event_repository import IInterviewEventRepository
from src.domain.interfaces.session.session_lock import ISessionLock
from src.domain.interfaces.session.session_presence import ISessionPresence
from src.domain.services.interview_planner import InterviewPlanner
from src.domain.services.journal_folder import JournalFolder


class InterviewSessionService(IInterviewSessionService):
    def __init__(
        self,
        token_verifier: IAttemptTokenVerifier,
        context_client: IAssessmentContextClient,
        lock: ISessionLock,
        presence: ISessionPresence,
        event_repository: IInterviewEventRepository,
        cv_loader: CvLoader,
        evidence_recorder: EvidenceRecorder,
        interviewer_turn: InterviewerTurn,
        completion_publisher: CompletionPublisher,
        clock: Callable[[], datetime],
    ) -> None:
        self._token_verifier = token_verifier
        self._context_client = context_client
        self._lock = lock
        self._presence = presence
        self._event_repository = event_repository
        self._cv_loader = cv_loader
        self._evidence_recorder = evidence_recorder
        self._interviewer_turn = interviewer_turn
        self._completion_publisher = completion_publisher
        self._clock = clock

    async def open_connection(self, token: str) -> InterviewConnection:
        attempt_id = self._token_verifier.verify(token)
        context = await self._context_client.get_context(attempt_id)
        if context.attempt_id != attempt_id:
            raise AssessmentContextUnavailableError()
        return InterviewConnection(attempt_id=attempt_id, context=context)

    async def register_connection(self, connection: InterviewConnection) -> str:
        return await self._presence.claim(str(connection.attempt_id))

    async def transcript(
        self, connection: InterviewConnection, last_event_id: UUID | None
    ) -> list[TranscriptEntry | SessionFinished]:
        events = await self._event_repository.list_events(str(connection.attempt_id))
        known = {event.event_id for event in events}
        skipping = last_event_id is not None and last_event_id in known
        entries: list[TranscriptEntry | SessionFinished] = []
        for event in events:
            if skipping:
                skipping = event.event_id != last_event_id
                continue
            entry = SessionOutputMapper.transcript_entry(event)
            if entry is not None:
                entries.append(entry)
        return entries

    async def open_session(self, connection: InterviewConnection) -> AsyncIterator[SessionOutput]:
        session_id = str(connection.attempt_id)
        async with self._lock.hold(session_id):
            events = await self._event_repository.list_events(session_id)
            if not events:
                events = [await self._start(connection, session_id)]
            state = JournalFolder.fold(events)
            if state.status == SessionStatus.COMPLETED:
                await self._completion_publisher.publish(connection, session_id)
                return
            if InterviewPlanner(connection.context.template).pending_question(state) is not None:
                return
            turn_id = uuid4()
            last_message_seq = max(state.messages, default=None)
            if last_message_seq is not None and state.messages[last_message_seq].role == "candidate":
                answer = next(
                    e for e in reversed(events) if isinstance(e, CandidateMessage) and e.seq == last_message_seq
                )
                await self._evidence_recorder.record(connection, events, answer)
                turn_id = answer.turn_id
            async for output in self._interviewer_turn.run(connection, events, turn_id):
                yield output

    async def answer(self, connection: InterviewConnection, turn_id: UUID, text: str) -> AsyncIterator[SessionOutput]:
        session_id = str(connection.attempt_id)
        async with self._lock.hold(session_id):
            events = await self._event_repository.list_events(session_id)
            if not events:
                raise NoPendingQuestionError()
            state = JournalFolder.fold(events)
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
                if InterviewPlanner(connection.context.template).pending_question(state) is None:
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

            await self._evidence_recorder.record(connection, events, existing)
            async for output in self._interviewer_turn.run(connection, events, turn_id):
                yield output

    async def pause(self, connection: InterviewConnection, token: str) -> None:
        session_id = str(connection.attempt_id)
        if not await self._presence.release(session_id, token):
            return
        async with self._lock.hold(session_id):
            events = await self._event_repository.list_events(session_id)
            if not events or JournalFolder.fold(events).status != SessionStatus.IN_PROGRESS:
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

    async def _start(self, connection: InterviewConnection, session_id: str) -> SessionStarted:
        cv = await self._cv_loader.load(connection)
        started = SessionStarted(
            event_id=uuid4(),
            session_id=session_id,
            seq=1,
            occurred_at=self._clock(),
            attempt_id=connection.attempt_id,
            template_version=connection.context.template_version,
            cv_attached=cv is not None,
        )
        await self._event_repository.append(started)
        return started

    @staticmethod
    def _find_answer(events: list[SessionEvent], turn_id: UUID) -> CandidateMessage | None:
        return next((e for e in events if isinstance(e, CandidateMessage) and e.turn_id == turn_id), None)

    @staticmethod
    def _replies_to(events: list[SessionEvent], answer: CandidateMessage) -> list[SessionOutput]:
        replies: list[SessionOutput] = []
        for event in events:
            if event.seq <= answer.seq:
                continue
            if isinstance(event, InterviewerMessage) and event.turn_id == answer.turn_id:
                replies.append(SessionOutputMapper.message_completed(event))
            elif isinstance(event, SessionCompleted) and replies:
                replies.append(SessionOutputMapper.session_finished(event))
        return replies
