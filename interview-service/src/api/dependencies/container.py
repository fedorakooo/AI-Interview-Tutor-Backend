from typing import Annotated, Protocol

from fastapi import Depends
from starlette.requests import HTTPConnection

from src.application.interfaces.assessment_report_service import IAssessmentReportService
from src.application.interfaces.candidate_feedback_service import ICandidateFeedbackService
from src.application.interfaces.data_erasure_service import IDataErasureService
from src.application.interfaces.interview_session_service import IInterviewSessionService
from src.application.interfaces.template_draft_service import ITemplateDraftService


class ApiContainer(Protocol):
    interview_session_service: IInterviewSessionService
    assessment_report_service: IAssessmentReportService
    candidate_feedback_service: ICandidateFeedbackService
    template_draft_service: ITemplateDraftService
    data_erasure_service: IDataErasureService


def get_container(connection: HTTPConnection) -> ApiContainer:
    return connection.app.state.container


ContainerDep = Annotated[ApiContainer, Depends(get_container)]
