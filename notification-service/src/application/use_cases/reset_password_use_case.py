from shared_models.messaging.reset_password import ResetPasswordMessage

from src.domain.exceptions.not_sent_error import NotSentError
from src.domain.ports.outbound.abstract_mongo_repository import AbstractMongoRepository
from src.domain.ports.outbound.abstract_ses_client import AbstractSESClient


class ResetPasswordUseCase:
    """UseCase to reset user password."""

    def __init__(self, mongo_repository: AbstractMongoRepository, ses_client: AbstractSESClient):
        self.mongo_repository = mongo_repository
        self.ses_client = ses_client

    def __call__(self, event_data: dict) -> None:
        message = ResetPasswordMessage.model_validate(event_data)

        self.mongo_repository.insert_one(message.model_dump(mode="json"))

        is_sent = False
        send_attempts = 0

        with self.mongo_repository:
            while not is_sent and send_attempts < 5:
                is_sent = self.ses_client.send_email(message.email, message.subject, message.body)
                send_attempts += 1

        if not is_sent:
            raise NotSentError(
                recipient=message.email,
                attempts=send_attempts,
            )
