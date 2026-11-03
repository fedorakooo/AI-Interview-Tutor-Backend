import asyncio
import logging
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError
from shared_models.feature_flags.flags import feature_enabled

from src.api.dependencies.container import ApiContainer
from src.api.errors.error_mapping import ErrorSpec, resolve_error_spec
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
from src.application.dtos.message_completed import MessageCompleted
from src.application.dtos.message_delta import MessageDelta
from src.application.dtos.session_finished import SessionFinished
from src.application.dtos.session_output import SessionOutput
from src.application.dtos.transcript_entry import TranscriptEntry
from src.config import settings
from src.domain.entities.interview_connection import InterviewConnection
from src.domain.exceptions.interview_service_error import InterviewServiceError

logger = logging.getLogger(__name__)

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


async def _send_error(websocket: WebSocket, exc: BaseException) -> ErrorSpec:
    spec = resolve_error_spec(exc)
    await _send(
        websocket,
        ServerError(code=spec.ws_code or ErrorCode.INTERNAL_ERROR, message=spec.detail, retryable=spec.retryable),
    )
    return spec


async def _open_connection(
    websocket: WebSocket, hello: ClientHello, container: ApiContainer
) -> InterviewConnection | None:
    try:
        return await container.interview_session_service.open_connection(hello.token)
    except InterviewServiceError as exc:
        spec = await _send_error(websocket, exc)
        await websocket.close(code=spec.ws_close_code or status.WS_1011_INTERNAL_ERROR)
        return None


async def _replay(websocket: WebSocket, entries: list[TranscriptEntry | SessionFinished]) -> None:
    for entry in entries:
        if isinstance(entry, TranscriptEntry):
            await _send(
                websocket,
                ServerTranscriptEntry(
                    event_id=entry.event_id,
                    seq=entry.seq,
                    role=entry.role,
                    text=entry.text,
                    occurred_at=entry.occurred_at,
                ),
            )
        else:
            await _send(websocket, ServerSessionCompleted(event_id=entry.event_id, seq=entry.seq))


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
        elif isinstance(output, MessageCompleted):
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
        elif isinstance(output, SessionFinished):
            await _send(websocket, ServerSessionCompleted(event_id=output.event_id, seq=output.seq))


async def _stream_guarded(websocket: WebSocket, outputs: AsyncIterator[SessionOutput]) -> bool:
    try:
        await _stream(websocket, outputs)
    except WebSocketDisconnect:
        raise
    except Exception as exc:
        spec = await _send_error(websocket, exc)
        if spec.ws_close_code is not None:
            await websocket.close(code=spec.ws_close_code)
            return False
    return True


@router.websocket("/ws")
async def interview_ws(websocket: WebSocket) -> None:
    if not feature_enabled("EMPLOYER_ASSESSMENT_DEMO", False):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    container: ApiContainer = websocket.app.state.container
    await websocket.accept()
    hello = await _receive_hello(websocket)
    if hello is None:
        return
    connection = await _open_connection(websocket, hello, container)
    if connection is None:
        return

    await _send(
        websocket,
        ServerReady(
            attempt_id=connection.attempt_id,
            language=connection.language,
            question_count=connection.question_count,
            duration_minutes=connection.duration_minutes,
            last_event_id=hello.last_event_id,
        ),
    )

    presence_token: str | None = None
    try:
        presence_token = await container.interview_session_service.register_connection(connection)
        await _replay(websocket, await container.interview_session_service.transcript(connection, hello.last_event_id))
        if not await _stream_guarded(websocket, container.interview_session_service.open_session(connection)):
            return
        while True:
            message = _parse_client_message(await websocket.receive_text())
            if isinstance(message, ClientPing):
                await _send(websocket, ServerPong())
            elif isinstance(message, ClientCandidateMessage):
                outputs = container.interview_session_service.answer(connection, message.turn_id, message.text)
                if not await _stream_guarded(websocket, outputs):
                    return
            else:
                await _send(websocket, ServerError(code=ErrorCode.INVALID_MESSAGE, message="Unexpected message"))
    except WebSocketDisconnect:
        pass
    finally:
        try:
            if presence_token is not None:
                await container.interview_session_service.pause(connection, presence_token)
        except Exception:
            logger.exception("Pausing the interview session failed for attempt %s", connection.attempt_id)
