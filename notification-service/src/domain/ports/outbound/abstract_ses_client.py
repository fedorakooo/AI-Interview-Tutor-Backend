from abc import ABC, abstractmethod


class AbstractSESClient(ABC):
    """Sends an email to the specified recipient."""

    @abstractmethod
    def send_email(self, recipient: str, subject: str, body_text: str) -> bool:
        pass
