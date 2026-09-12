import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from jwt_handler.value_objects import AccessTokenPayload
from shared_models.interview.mode import InterviewMode, InterviewStartConfig

from src.api.dependencies.entitlements import check_interview_quota_for_user, record_interview_started
from src.api.dependencies.interview import InterviewManagerDep
from src.api.dependencies.mongo import get_cv_analysis_repository
from src.api.security import verify_ws_token
from src.domain.exceptions.cv_not_ready_error import CVNotReadyError
from src.domain.interfaces.mongo import IMongoRepository
from src.domain.models.user_profile import UserProfile
from src.logger import app_logger
from shared_models.feature_flags.flags import feature_enabled
from src.services.cv_data_resolver import CVDataResolver
from src.services.voice import build_voice_stack

router = APIRouter(prefix="/interview", tags=["Interview"])

CV_NOT_READY_CLOSE_CODE = 4001


def get_cv_data_resolver(
    mongo_repository: Annotated[IMongoRepository, Depends(get_cv_analysis_repository)],
) -> CVDataResolver:
    return CVDataResolver(mongo_repository=mongo_repository)


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: UUID,
    interview_manager: InterviewManagerDep,
    _: Annotated[AccessTokenPayload, Depends(verify_ws_token)],
    cv_data_resolver: Annotated[CVDataResolver, Depends(get_cv_data_resolver)],
    mode: str = Query(default="mixed"),
    resume_session_id: str | None = Query(default=None),
    company_preset: str | None = Query(default=None),
    role_track: str | None = Query(default=None),
    language: str = Query(default="en"),
    voice_enabled: bool = Query(default=False),
) -> None:
    user = UserProfile(id=user_id)
    user_id_str = str(user.id)

    try:
        await check_interview_quota_for_user(user_id_str)
    except HTTPException as exc:
        await websocket.accept()
        await websocket.send_text(json.dumps({"type": "error", "code": "INTERVIEW_QUOTA_EXCEEDED", "message": exc.detail}))
        await websocket.close(code=4402)
        return

    try:
        resolution = await cv_data_resolver.resolve(user_id_str)
    except CVNotReadyError as exc:
        await websocket.accept()
        await websocket.send_text(
            json.dumps(
                {
                    "type": "error",
                    "code": "CV_NOT_READY",
                    "message": exc.message,
                }
            )
        )
        await websocket.close(code=CV_NOT_READY_CLOSE_CODE)
        return

    if voice_enabled and not feature_enabled("VOICE_INTERVIEW", False):
        voice_enabled = False

    try:
        interview_mode = InterviewMode(mode)
    except ValueError:
        interview_mode = InterviewMode.MIXED

    _stt, _tts = build_voice_stack()

    start_config = InterviewStartConfig(
        mode=interview_mode,
        company_preset=company_preset,
        role_track=role_track,
        language=language,
        voice_enabled=voice_enabled,
    )

    session_id = await interview_manager.start_interview(
        websocket,
        user,
        resolution.cv_data,
        cv_correlation_id=resolution.correlation_id,
        start_config=start_config,
        resume_session_id=resume_session_id,
    )
    await record_interview_started(user_id)

    await websocket.send_text(
        json.dumps(
            {
                "type": "interview_started",
                "user_id": user_id_str,
                "session_id": session_id,
                "cv_source": resolution.source,
                "correlation_id": resolution.correlation_id,
                "mode": interview_mode.value,
                "voice_enabled": voice_enabled,
            }
        )
    )

    try:
        while True:
            data = await websocket.receive_text()

            message_data = json.loads(data)
            message_type = message_data.get("type", "message")

            if message_type == "user_message":
                content = message_data.get("content", "")
                if content:
                    await interview_manager.handle_user_message(session_id, content)
                else:
                    await websocket.send_text(json.dumps({"type": "error", "message": "Message content is required"}))

            elif message_type == "start_config":
                # Allow late JD attachment for personalization context.
                jd = message_data.get("job_description")
                if jd and hasattr(interview_manager, "attach_job_description"):
                    await interview_manager.attach_job_description(session_id, jd)

            elif message_type == "voice_chunk":
                # Voice STT bridge: client sends transcribed text or base64 audio metadata.
                transcript = message_data.get("transcript") or message_data.get("content", "")
                if transcript:
                    await interview_manager.handle_user_message(session_id, transcript)

            elif message_type == "end_interview":
                await interview_manager.end_interview(session_id)
                break

            elif message_type == "get_status":
                status_payload = interview_manager.get_interview_status(session_id)
                if status_payload:
                    await websocket.send_text(json.dumps({"type": "interview_status", "status": status_payload}))

            else:
                content = message_data.get("content", data)
                await interview_manager.handle_user_message(session_id, content)

    except WebSocketDisconnect:
        app_logger.info("WebSocket disconnected for session %s", session_id)
        await interview_manager.disconnect_user(session_id)
