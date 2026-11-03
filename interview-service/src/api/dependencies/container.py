from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import Depends
from shared_models.assessment import (
    AssessmentOverview,
    AssessmentTemplateSnapshot,
    ErasureResult,
    FeedbackView,
    FocusDetail,
    ReviewRequest,
    SessionEvent,
    TemplateDraftRequest,
)
from starlette.requests import HTTPConnection

from src.application.dtos.session_output import SessionOutput
from src.domain.entities.interview_connection import InterviewConnection


class ApiContainer(Protocol):
    open_interview_connection_use_case: Callable[[str], Awaitable[InterviewConnection]]
    list_interview_events_use_case: Callable[[InterviewConnection], Awaitable[list[SessionEvent]]]
    register_interview_connection_use_case: Callable[[InterviewConnection], Awaitable[str]]
    open_interview_session_use_case: Callable[[InterviewConnection], AsyncIterator[SessionOutput]]
    handle_candidate_answer_use_case: Callable[[InterviewConnection, UUID, str], AsyncIterator[SessionOutput]]
    pause_interview_session_use_case: Callable[[InterviewConnection, str], Awaitable[None]]
    get_assessment_template_use_case: Callable[[UUID], Awaitable[AssessmentTemplateSnapshot]]
    get_assessment_overview_use_case: Callable[[UUID, AssessmentTemplateSnapshot], Awaitable[AssessmentOverview]]
    get_focus_detail_use_case: Callable[[UUID, AssessmentTemplateSnapshot, str], Awaitable[FocusDetail]]
    add_focus_review_use_case: Callable[[UUID, AssessmentTemplateSnapshot, str, ReviewRequest], Awaitable[FocusDetail]]
    get_candidate_feedback_use_case: Callable[[UUID, AssessmentTemplateSnapshot], Awaitable[FeedbackView]]
    edit_candidate_feedback_use_case: Callable[[UUID, AssessmentTemplateSnapshot, UUID, str], Awaitable[FeedbackView]]
    create_template_draft_use_case: Callable[[TemplateDraftRequest], Awaitable[AssessmentTemplateSnapshot]]
    erase_attempt_data_use_case: Callable[[UUID, UUID | None], Awaitable[ErasureResult]]


def get_container(connection: HTTPConnection) -> ApiContainer:
    return connection.app.state.container


ContainerDep = Annotated[ApiContainer, Depends(get_container)]
