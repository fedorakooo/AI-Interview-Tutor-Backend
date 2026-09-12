from __future__ import annotations

import json
import time
from collections import defaultdict
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from shared_models.interview.mode import InterviewMode, InterviewStartConfig

from src.agent.data.sample_data import SAMPLE_CV
from src.api.dependencies.interview import InterviewManagerDep
from src.config import settings
from src.domain.models.user_profile import UserProfile
from src.logger import app_logger

router = APIRouter(prefix="/interview", tags=["Interview Sample"])

_SAMPLE_HITS: dict[str, list[float]] = defaultdict(list)
GUEST_USER_ID = UUID("00000000-0000-4000-8000-000000000001")


class SampleInterviewInfo(BaseModel):
    available: bool
    mode: str = "mixed"
    max_questions: int = 3
    voice_enabled: bool = False
    ws_path: str = "/api/v1/interview/ws/sample"


def _check_rate_limit(client_key: str) -> None:
    now = time.time()
    window = 3600
    limit = settings.sample_interview_rate_limit_per_hour
    hits = [ts for ts in _SAMPLE_HITS[client_key] if now - ts < window]
    _SAMPLE_HITS[client_key] = hits
    if len(hits) >= limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Sample interview rate limit exceeded")
    hits.append(now)


@router.get("/sample", response_model=SampleInterviewInfo)
async def sample_interview_info() -> SampleInterviewInfo:
    return SampleInterviewInfo(available=True)


@router.websocket("/ws/sample")
async def sample_interview_ws(
    websocket: WebSocket,
    interview_manager: InterviewManagerDep,
    sample: bool = Query(default=True),
    client_id: str | None = Query(default=None),
) -> None:
    if not sample:
        await websocket.close(code=4403)
        return

    client_key = client_id or websocket.client.host if websocket.client else "anonymous"
    try:
        _check_rate_limit(client_key)
    except HTTPException:
        await websocket.accept()
        await websocket.send_text(json.dumps({"type": "error", "code": "RATE_LIMIT", "message": "Too many sample sessions"}))
        await websocket.close(code=4429)
        return

    user = UserProfile(id=GUEST_USER_ID)
    start_config = InterviewStartConfig(mode=InterviewMode.MIXED, voice_enabled=False)
    session_id = await interview_manager.start_interview(
        websocket,
        user,
        SAMPLE_CV,
        cv_correlation_id=f"sample-{uuid4()}",
        start_config=start_config,
    )

    await websocket.send_text(
        json.dumps(
            {
                "type": "interview_started",
                "session_id": session_id,
                "sample": True,
                "max_questions": 3,
                "cv_source": "sample",
            }
        )
    )

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            message_type = message_data.get("type", "message")
            if message_type == "end_interview":
                await interview_manager.end_interview(session_id)
                break
            transcript = message_data.get("transcript") or message_data.get("content", "")
            if transcript:
                await interview_manager.handle_user_message(session_id, transcript)
    except WebSocketDisconnect:
        app_logger.info("Sample interview disconnected session=%s", session_id)
        await interview_manager.disconnect_user(session_id)
