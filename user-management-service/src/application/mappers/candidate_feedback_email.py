from datetime import datetime

from shared_models.messaging.notifications import NotificationEmailMessage

CANDIDATE_FEEDBACK_EVENT_TYPE = "candidate_feedback_email.v1"
CANDIDATE_FEEDBACK_EMAIL_TYPE = "candidate_feedback"


def build_candidate_feedback_email(payload: dict, email: str, now: datetime) -> str:
    """Join the stored approved text with the candidate address, which never enters the outbox payload."""
    return NotificationEmailMessage(
        user_id=str(payload["attempt_id"]),
        email=email,
        subject=payload["subject"],
        body=payload["body"],
        email_type=CANDIDATE_FEEDBACK_EMAIL_TYPE,
        published_at=now.isoformat(),
    ).model_dump_json()
