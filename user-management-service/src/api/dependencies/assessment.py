from src.config import settings
from src.infrastructure.auth.invitation_token_handler import InvitationTokenHandler


def get_invitation_token_handler() -> InvitationTokenHandler:
    return InvitationTokenHandler(settings.assessment_settings.invitation_token_pepper)
