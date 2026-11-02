from fastapi import WebSocket
from jwt_handler.handlers import CandidateInterviewTokenVerifier

from src.application.interview.session_service import InterviewSessionService
from src.application.use_cases.open_interview_connection import OpenInterviewConnectionUseCase
from src.config import settings


def get_open_interview_connection_use_case(websocket: WebSocket) -> OpenInterviewConnectionUseCase:
    return OpenInterviewConnectionUseCase(
        token_verifier=CandidateInterviewTokenVerifier(public_key=settings.jwt_settings.public_key),
        context_client=websocket.app.state.assessment_context_client,
    )


def get_interview_session_service(websocket: WebSocket) -> InterviewSessionService:
    return websocket.app.state.interview_session_service
