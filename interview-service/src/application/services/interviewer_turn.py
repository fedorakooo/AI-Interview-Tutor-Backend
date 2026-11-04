from collections.abc import AsyncIterator, Callable
from datetime import datetime
from uuid import UUID, uuid4

from src.application.dtos.message_delta import MessageDelta
from src.application.dtos.session_output import SessionOutput
from src.application.mappers.session_output_mapper import SessionOutputMapper
from src.application.services.completion_publisher import CompletionPublisher
from src.application.services.cv_loader import CvLoader
from src.domain.entities.interview_connection import InterviewConnection
from src.domain.entities.session_state import SessionState
from src.domain.enums.message_kind import MessageKind
from src.domain.events.candidate_message import CandidateMessage
from src.domain.events.interviewer_message import InterviewerMessage
from src.domain.events.session_completed import SessionCompleted
from src.domain.events.session_event import SessionEvent
from src.domain.exceptions.session_errors import EmptyInterviewerMessageError
from src.domain.interfaces.ai.interviewer_agent import IInterviewerAgent
from src.domain.interfaces.repositories.interview_event_repository import IInterviewEventRepository
from src.domain.services.interview_planner import InterviewPlanner
from src.domain.services.journal_folder import JournalFolder
from src.domain.value_objects.ask_focus import AskFocus
from src.domain.value_objects.ask_intro import AskIntro
from src.domain.value_objects.candidate_cv import CandidateCv
from src.domain.value_objects.complete import Complete
from src.domain.value_objects.interviewer_request import InterviewerRequest
from src.domain.value_objects.next_action import NextAction

TRANSCRIPT_TAIL = 8


class InterviewerTurn:
    def __init__(
        self,
        event_repository: IInterviewEventRepository,
        interviewer: IInterviewerAgent,
        cv_loader: CvLoader,
        completion_publisher: CompletionPublisher,
        clock: Callable[[], datetime],
    ) -> None:
        self._event_repository = event_repository
        self._interviewer = interviewer
        self._cv_loader = cv_loader
        self._completion_publisher = completion_publisher
        self._clock = clock

    async def run(
        self, connection: InterviewConnection, events: list[SessionEvent], turn_id: UUID
    ) -> AsyncIterator[SessionOutput]:
        template = connection.context.template
        state = JournalFolder.fold(events)
        action = InterviewPlanner(template).next_action(state, state.active_elapsed(self._clock()))
        closing = self._unfinished_closing(events) if isinstance(action, Complete) else None
        if closing is not None:
            yield SessionOutputMapper.message_completed(closing)
            async for output in self._complete(connection, events, state.session_id, action):
                yield output
            return
        cv = await self._cv_loader.load(connection) if state.cv_attached else None
        request = self._request(connection, state, action, cv)

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
        await self._event_repository.append(message)
        events.append(message)
        yield SessionOutputMapper.message_completed(message)

        if isinstance(action, Complete):
            async for output in self._complete(connection, events, state.session_id, action):
                yield output

    async def _complete(
        self, connection: InterviewConnection, events: list[SessionEvent], session_id: str, action: Complete
    ) -> AsyncIterator[SessionOutput]:
        completed = SessionCompleted(
            event_id=uuid4(),
            session_id=session_id,
            seq=events[-1].seq + 1,
            occurred_at=self._clock(),
            reason=action.reason,
        )
        await self._event_repository.append(completed)
        events.append(completed)
        yield SessionOutputMapper.session_finished(completed)
        await self._completion_publisher.publish(connection, session_id)

    @staticmethod
    def _unfinished_closing(events: list[SessionEvent]) -> InterviewerMessage | None:
        last_message = next(
            (event for event in reversed(events) if isinstance(event, (InterviewerMessage, CandidateMessage))), None
        )
        if isinstance(last_message, InterviewerMessage) and last_message.kind == MessageKind.CLOSING:
            return last_message
        return None

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
        raise EmptyInterviewerMessageError()

    @staticmethod
    def _request(
        connection: InterviewConnection, state: SessionState, action: NextAction, cv: CandidateCv | None
    ) -> InterviewerRequest:
        template = connection.context.template
        focus = template.focus_by_id(action.focus_id) if isinstance(action, AskFocus) else None
        custom = None
        if isinstance(action, AskFocus) and action.custom_question_index is not None:
            custom = template.custom_questions[action.custom_question_index]
        tail = tuple(state.messages[seq] for seq in sorted(state.messages))[-TRANSCRIPT_TAIL:]
        return InterviewerRequest(
            template=template,
            action=action,
            focus=focus,
            custom_question=custom,
            coverage=state.coverage.get(focus.id) if focus else None,
            cv=cv,
            transcript=tail,
        )
