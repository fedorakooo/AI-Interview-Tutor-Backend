from typing import Protocol


class IMessagePublisher(Protocol):
    """Outbound messaging port for publishing RabbitMQ jobs and events."""

    async def publish(self, queue_name: str, message: str) -> None:
        """Publish a persistent JSON message to the named durable queue."""
        pass
