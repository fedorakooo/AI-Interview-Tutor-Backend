from src.config import settings
from src.domain.interfaces.reports.interview_report_client import IInterviewReportClient
from src.infrastructure.auth.invitation_token_handler import InvitationTokenHandler
from src.infrastructure.interview_service.report_client import InterviewServiceReportClient


def get_invitation_token_handler() -> InvitationTokenHandler:
    return InvitationTokenHandler(settings.assessment_settings.invitation_token_pepper)


def get_interview_report_client() -> IInterviewReportClient:
    return InterviewServiceReportClient(
        base_url=settings.interview_service_settings.url,
        service_token=settings.assessment_settings.internal_service_token,
        timeout_seconds=settings.interview_service_settings.timeout_seconds,
    )
