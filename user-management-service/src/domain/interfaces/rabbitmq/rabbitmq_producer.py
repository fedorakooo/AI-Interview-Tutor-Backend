from abc import ABC, abstractmethod


class IRabbitMQProducer(ABC):
    """Interface defining message broker controls."""

    @abstractmethod
    async def send_message(self, message: str) -> None:
        """Sends a message to the message broker."""
        pass
