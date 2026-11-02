from src.config import settings
from src.domain.interfaces.reports.interview_report_client import IInterviewReportClient
from src.domain.interfaces.reports.interview_spec_client import IInterviewSpecClient
from src.infrastructure.auth.invitation_token_handler import InvitationTokenHandler
from src.infrastructure.interview_service.report_client import InterviewServiceReportClient
from src.infrastructure.interview_service.spec_client import InterviewServiceSpecClient


def get_invitation_token_handler() -> InvitationTokenHandler:
    return InvitationTokenHandler(settings.assessment_settings.invitation_token_pepper)


def get_interview_report_client() -> IInterviewReportClient:
    return InterviewServiceReportClient(
        base_url=settings.interview_service_settings.url,
        service_token=settings.assessment_settings.internal_service_token,
        timeout_seconds=settings.interview_service_settings.timeout_seconds,
    )


def get_interview_spec_client() -> IInterviewSpecClient:
    return InterviewServiceSpecClient(
        base_url=settings.interview_service_settings.url,
        service_token=settings.assessment_settings.internal_service_token,
        timeout_seconds=settings.interview_service_settings.timeout_seconds,
    )
