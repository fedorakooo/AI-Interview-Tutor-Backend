from logging import Logger

from botocore.client import BaseClient
from botocore.exceptions import ClientError

from src.domain.ports.outbound.abstract_ses_client import AbstractSESClient


class SESClient(AbstractSESClient):
    def __init__(
        self,
        client: BaseClient,
        sender_email: str,
        logger: Logger,
    ):
        self._client = client
        self.sender_email = sender_email
        self.logger = logger

    def send_email(self, recipient: str, subject: str, body_text: str, *, html_body: str | None = None) -> bool:
        destination = {"ToAddresses": [recipient]}
        body: dict = {"Text": {"Charset": "UTF-8", "Data": body_text}}
        if html_body:
            body["Html"] = {"Charset": "UTF-8", "Data": html_body}
        message = {
            "Body": body,
            "Subject": {"Charset": "UTF-8", "Data": subject},
        }

        kwargs = {
            "Destination": destination,
            "Message": message,
            "Source": self.sender_email,
        }

        try:
            self._client.send_email(**kwargs)
            return True
        except ClientError as exc:
            self.logger.error(f"Error sending email: {exc}")
            return False
