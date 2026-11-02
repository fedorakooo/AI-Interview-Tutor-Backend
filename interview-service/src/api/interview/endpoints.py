import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError
from shared_models.feature_flags.flags import feature_enabled

from src.api.interview.dependencies import get_open_interview_connection_use_case
from src.api.interview.protocol import (
    PROTOCOL_VERSION,
    ClientCandidateMessage,
    ClientHello,
    ClientMessageAdapter,
    ClientPing,
    ErrorCode,
    ServerError,
    ServerMessage,
    ServerPong,
    ServerReady,
)
from src.application.use_cases.open_interview_connection import OpenInterviewConnectionUseCase
from src.config import settings
from src.domain.entities.interview_connection import InterviewConnection
from src.domain.exceptions.assessment_context_errors import (
    AssessmentContextNotFoundError,
    AssessmentContextUnavailableError,
    AssessmentNotReadyError,
)
from src.domain.exceptions.attempt_token_error import InvalidAttemptTokenError

router = APIRouter(prefix="/api/v2/interview", tags=["Interview"])


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
    websocket: WebSocket,
    hello: ClientHello,
    use_case: OpenInterviewConnectionUseCase,
) -> InterviewConnection | None:
    try:
        return await use_case(hello.token)
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


@router.websocket("/ws")
async def interview_ws(
    websocket: WebSocket,
    use_case: Annotated[OpenInterviewConnectionUseCase, Depends(get_open_interview_connection_use_case)],
) -> None:
    if not feature_enabled("EMPLOYER_ASSESSMENT_DEMO", False):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    hello = await _receive_hello(websocket)
    if hello is None:
        return
    connection = await _open_connection(websocket, hello, use_case)
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

    try:
        while True:
            message = _parse_client_message(await websocket.receive_text())
            if isinstance(message, ClientPing):
                await _send(websocket, ServerPong())
            elif isinstance(message, ClientCandidateMessage):
                await _send(
                    websocket,
                    ServerError(code=ErrorCode.ENGINE_UNAVAILABLE, message="Interview engine is not available"),
                )
            else:
                await _send(websocket, ServerError(code=ErrorCode.INVALID_MESSAGE, message="Unexpected message"))
    except WebSocketDisconnect:
        return
