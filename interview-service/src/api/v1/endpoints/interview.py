from typing import Annotated
from uuid import UUID

import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from src.api.dependencies.mongo import get_cv_analysis_repository
from src.api.v1.managers.interview_manager import interview_manager
from src.domain.interfaces.mongo import IMongoRepository
from src.domain.models.user_profile import UserProfile
from src.logger import app_logger
from src.services.cv_data_resolver import CVDataResolver

router = APIRouter(prefix="/interview", tags=["Interview"])


def get_cv_data_resolver(
    mongo_repository: Annotated[IMongoRepository, Depends(get_cv_analysis_repository)],
) -> CVDataResolver:
    return CVDataResolver(mongo_repository=mongo_repository)


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: UUID,
    cv_data_resolver: Annotated[CVDataResolver, Depends(get_cv_data_resolver)],
) -> None:
    user = UserProfile(id=user_id)
    cv_data = await cv_data_resolver.resolve(str(user_id))

    user_id_str = str(user.id)

    await interview_manager.start_interview(websocket, user, cv_data)

    await websocket.send_text(
        json.dumps(
            {
                "type": "interview_started",
                "user_id": user_id_str,
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
