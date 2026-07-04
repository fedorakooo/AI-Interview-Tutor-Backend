from typing import Annotated

from fastapi import Depends, Request
from src.api.v1.managers.interview_manager import InterviewConnectionManager


def get_interview_manager(request: Request) -> InterviewConnectionManager:
    return request.app.state.interview_manager


InterviewManagerDep = Annotated[InterviewConnectionManager, Depends(get_interview_manager)]
