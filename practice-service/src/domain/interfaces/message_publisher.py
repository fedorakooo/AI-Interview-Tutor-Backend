from abc import ABC, abstractmethod


class IMessagePublisher(ABC):
    """Outbound messaging port for publishing RabbitMQ jobs and events."""

    @abstractmethod
    async def publish(self, queue_name: str, message: str) -> None:
        """Publish a persistent JSON message to the named durable queue."""
        pass
