from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from jwt_handler.value_objects import AccessTokenPayload
from shared_models.interview.report import InterviewReport
from shared_models.interview.session import InterviewSessionDocument, InterviewSessionStatus

from src.api.dependencies.mongo import get_interview_session_repository
from src.api.security import require_authenticated
from src.repositories.interview_session_repository import InterviewSessionRepository

router = APIRouter(prefix="/interview", tags=["Interview Sessions"])


@router.get("/sessions", response_model=list[InterviewSessionDocument])
async def list_sessions(
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    session_repository: Annotated[InterviewSessionRepository, Depends(get_interview_session_repository)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[InterviewSessionDocument]:
    return await session_repository.list_user_sessions(payload["id"], skip=skip, limit=limit)


@router.get("/sessions/{session_id}/report", response_model=InterviewReport)
async def get_session_report(
    session_id: str,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    session_repository: Annotated[InterviewSessionRepository, Depends(get_interview_session_repository)],
) -> InterviewReport:
    session = await session_repository.get_session(session_id)
    if not session or session.user_id != payload["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if session.status != InterviewSessionStatus.COMPLETED or session.report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not available")
    return session.report
