import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError
from shared_models.assessment import CandidateMessage, InterviewerMessage, SessionCompleted, SessionEvent
from shared_models.feature_flags.flags import feature_enabled

from src.api.v1.schemas.interview_protocol import (
    PROTOCOL_VERSION,
    ClientCandidateMessage,
    ClientHello,
    ClientMessageAdapter,
    ClientPing,
    ErrorCode,
    ServerError,
    ServerInterviewerMessageCompleted,
    ServerInterviewerMessageDelta,
    ServerInterviewerMessageStarted,
    ServerMessage,
    ServerPong,
    ServerReady,
    ServerSessionCompleted,
    ServerTranscriptEntry,
)
from src.app.container import AppContainer
from src.application.services.interview_turn_service import MessageDelta, SessionOutput
from src.config import settings
from src.domain.entities.interview_connection import InterviewConnection
from src.domain.exceptions.assessment_context_errors import (
    AssessmentContextNotFoundError,
    AssessmentContextUnavailableError,
    AssessmentNotReadyError,
)
from src.domain.exceptions.attempt_token_error import InvalidAttemptTokenError
from src.domain.exceptions.session_errors import NoPendingQuestionError, SessionBusyError, SessionCompletedError
from src.logger import app_logger

router = APIRouter(prefix="/interview", tags=["Interview"])


async def _send(websocket: WebSocket, message: ServerMessage) -> None:
    await websocket.send_text(message.model_dump_json())


async def _reject(websocket: WebSocket, code: ErrorCode, message: str, close_code: int) -> None:
    await _send(websocket, ServerError(code=code, message=message))
    await websocket.close(code=close_code)


def _parse_client_message(raw: str) -> ClientHello | ClientCandidateMessage | ClientPing | None:
    try:
        return ClientMessageAdapter.validate_json(raw)
    except ValidationError:
        return None


async def _receive_hello(websocket: WebSocket) -> ClientHello | None:
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=settings.interview_hello_timeout_seconds)
    except TimeoutError:
        await _reject(websocket, ErrorCode.INVALID_MESSAGE, "Hello message timed out", status.WS_1008_POLICY_VIOLATION)
        return None

    message = _parse_client_message(raw)
    if not isinstance(message, ClientHello):
        await _reject(websocket, ErrorCode.INVALID_MESSAGE, "Expected a hello message", status.WS_1008_POLICY_VIOLATION)
        return None
    if message.protocol_version != PROTOCOL_VERSION:
        await _reject(
            websocket,
            ErrorCode.UNSUPPORTED_PROTOCOL_VERSION,
            f"Supported protocol version is {PROTOCOL_VERSION}",
            status.WS_1008_POLICY_VIOLATION,
        )
        return None
    return message


async def _open_connection(
    websocket: WebSocket, hello: ClientHello, container: AppContainer
) -> InterviewConnection | None:
    try:
        return await container.open_interview_connection_use_case(hello.token)
    except InvalidAttemptTokenError:
        await _reject(websocket, ErrorCode.UNAUTHORIZED, "Invalid interview token", status.WS_1008_POLICY_VIOLATION)
    except AssessmentNotReadyError:
        await _reject(
            websocket, ErrorCode.ASSESSMENT_NOT_READY, "Assessment is not ready", status.WS_1008_POLICY_VIOLATION
        )
    except (AssessmentContextNotFoundError, AssessmentContextUnavailableError):
        await _reject(
            websocket, ErrorCode.ASSESSMENT_UNAVAILABLE, "Assessment is unavailable", status.WS_1011_INTERNAL_ERROR
        )
    return None


async def _replay(websocket: WebSocket, events: list[SessionEvent], last_event_id: UUID | None) -> None:
    known = {event.event_id for event in events}
    skipping = last_event_id is not None and last_event_id in known
    for event in events:
        if skipping:
            skipping = event.event_id != last_event_id
            continue
        if isinstance(event, InterviewerMessage | CandidateMessage):
            role = "interviewer" if isinstance(event, InterviewerMessage) else "candidate"
            await _send(
                websocket,
                ServerTranscriptEntry(
                    event_id=event.event_id, seq=event.seq, role=role, text=event.text, occurred_at=event.occurred_at
                ),
            )
        elif isinstance(event, SessionCompleted):
            await _send(websocket, ServerSessionCompleted(event_id=event.event_id, seq=event.seq))


async def _stream(websocket: WebSocket, outputs: AsyncIterator[SessionOutput]) -> None:
    started: set[UUID] = set()
    async for output in outputs:
        if isinstance(output, MessageDelta):
            if output.message_id not in started:
                started.add(output.message_id)
                await _send(
                    websocket, ServerInterviewerMessageStarted(turn_id=output.turn_id, message_id=output.message_id)
                )
            await _send(
                websocket,
                ServerInterviewerMessageDelta(turn_id=output.turn_id, message_id=output.message_id, delta=output.delta),
            )
        elif isinstance(output, InterviewerMessage):
            await _send(
                websocket,
                ServerInterviewerMessageCompleted(
                    turn_id=output.turn_id,
                    message_id=output.event_id,
                    event_id=output.event_id,
                    seq=output.seq,
                    text=output.text,
                ),
            )
        else:
            await _send(websocket, ServerSessionCompleted(event_id=output.event_id, seq=output.seq))


async def _stream_guarded(websocket: WebSocket, outputs: AsyncIterator[SessionOutput]) -> bool:
    try:
        await _stream(websocket, outputs)
    except SessionBusyError:
        await _send(websocket, ServerError(code=ErrorCode.SESSION_BUSY, message="Session is busy", retryable=True))
    except SessionCompletedError:
        await _send(websocket, ServerError(code=ErrorCode.SESSION_COMPLETED, message="Interview is completed"))
    except NoPendingQuestionError:
        await _send(websocket, ServerError(code=ErrorCode.INVALID_MESSAGE, message="No question is pending"))
    except AssessmentNotReadyError:
        await _reject(
            websocket, ErrorCode.ASSESSMENT_NOT_READY, "Assessment is not ready", status.WS_1008_POLICY_VIOLATION
        )
        return False
    except WebSocketDisconnect:
        raise
    except Exception:
        app_logger.exception("Interview turn failed")
        await _send(
            websocket,
            ServerError(code=ErrorCode.INTERNAL_ERROR, message="The interview turn failed", retryable=True),
        )
    return True


@router.websocket("/ws")
async def interview_ws(websocket: WebSocket) -> None:
    if not feature_enabled("EMPLOYER_ASSESSMENT_DEMO", False):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    container: AppContainer = websocket.app.state.container
    await websocket.accept()
    hello = await _receive_hello(websocket)
    if hello is None:
        return
    connection = await _open_connection(websocket, hello, container)
    if connection is None:
        return

    template = connection.context.template
    await _send(
        websocket,
        ServerReady(
            attempt_id=connection.attempt_id,
            language=template.language,
            question_count=template.question_count,
            duration_minutes=template.duration_minutes,
            last_event_id=hello.last_event_id,
        ),
    )

    presence_token: str | None = None
    try:
        presence_token = await container.register_interview_connection_use_case(connection)
        await _replay(websocket, await container.list_interview_events_use_case(connection), hello.last_event_id)
        if not await _stream_guarded(websocket, container.open_interview_session_use_case(connection)):
            return
        while True:
            message = _parse_client_message(await websocket.receive_text())
            if isinstance(message, ClientPing):
                await _send(websocket, ServerPong())
            elif isinstance(message, ClientCandidateMessage):
                outputs = container.handle_candidate_answer_use_case(connection, message.turn_id, message.text)
                if not await _stream_guarded(websocket, outputs):
                    return
            else:
                await _send(websocket, ServerError(code=ErrorCode.INVALID_MESSAGE, message="Unexpected message"))
    except WebSocketDisconnect:
        pass
    finally:
        try:
            if presence_token is not None:
                await container.pause_interview_session_use_case(connection, presence_token)
        except Exception:
            app_logger.exception("Pausing the interview session failed")
