from abc import ABC, abstractmethod


class MessageBrokerPort(ABC):
    """Abstract class defining the interface for message broker consumer operations."""

    @abstractmethod
    def process_messages(self) -> None:
        """Processes messages received from the broker."""
        pass
