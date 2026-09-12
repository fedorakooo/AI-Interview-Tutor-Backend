from shared_models.messaging.notifications import NotificationEmailMessage, VerifyEmailMessage

from src.application.email.html_templates import template_for_email_type
from src.domain.exceptions.not_sent_error import NotSentError
from src.domain.ports.outbound.abstract_mongo_repository import AbstractMongoRepository
from src.domain.ports.outbound.abstract_ses_client import AbstractSESClient


class SendNotificationEmailUseCase:
    """Send generic notification emails (verify, welcome, plan_ready, interview_complete)."""

    SUPPORTED_TYPES = {"email_verify", "welcome", "plan_ready", "interview_complete", "digest"}

    def __init__(self, mongo_repository: AbstractMongoRepository, ses_client: AbstractSESClient):
        self.mongo_repository = mongo_repository
        self.ses_client = ses_client

    def __call__(self, event_data: dict) -> None:
        email_type = event_data.get("email_type", "notification")
        if email_type == "email_verify":
            message = VerifyEmailMessage.model_validate(event_data)
        else:
            message = NotificationEmailMessage.model_validate(event_data)

        if message.email_type not in self.SUPPORTED_TYPES and email_type != "email_verify":
            message = NotificationEmailMessage.model_validate({**event_data, "email_type": email_type})

        self.mongo_repository.insert_one(message.model_dump(mode="json"))
        subject, html_body = template_for_email_type(message.email_type, subject=message.subject, body=message.body)

        is_sent = False
        send_attempts = 0
        with self.mongo_repository:
            while not is_sent and send_attempts < 5:
                is_sent = self.ses_client.send_email(
                    message.email,
                    subject,
                    message.body,
                    html_body=html_body,
                )
                send_attempts += 1

        if not is_sent:
            raise NotSentError(recipient=message.email, attempts=send_attempts)
