import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from jwt_handler.value_objects import AccessTokenPayload

from src.api.dependencies.mongo import get_cv_analysis_repository
from src.api.security import verify_ws_token
from src.api.v1.managers.interview_manager import interview_manager
from src.domain.exceptions.cv_not_ready_error import CVNotReadyError
from src.domain.interfaces.mongo import IMongoRepository
from src.domain.models.user_profile import UserProfile
from src.logger import app_logger
from src.services.cv_data_resolver import CVDataResolver

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
    _: Annotated[AccessTokenPayload, Depends(verify_ws_token)],
    cv_data_resolver: Annotated[CVDataResolver, Depends(get_cv_data_resolver)],
) -> None:
    user = UserProfile(id=user_id)
    user_id_str = str(user.id)

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

    await interview_manager.start_interview(websocket, user, resolution.cv_data)

    await websocket.send_text(
        json.dumps(
            {
                "type": "interview_started",
                "user_id": user_id_str,
                "cv_source": resolution.source,
                "correlation_id": resolution.correlation_id,
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
                    await interview_manager.handle_user_message(user_id_str, content)
                else:
                    await websocket.send_text(json.dumps({"type": "error", "message": "Message content is required"}))

            elif message_type == "end_interview":
                await interview_manager.end_interview(user_id_str)
                break

            elif message_type == "get_status":
                status = interview_manager.get_interview_status(user_id_str)
                if status:
                    await websocket.send_text(json.dumps({"type": "interview_status", "status": status}))

            else:
                content = message_data.get("content", data)
                await interview_manager.handle_user_message(user_id_str, content)

    except WebSocketDisconnect:
        app_logger.info(f"WebSocket disconnected for interview {user_id_str}")
        interview_manager.disconnect_user(user_id_str)

    await websocket.close()
