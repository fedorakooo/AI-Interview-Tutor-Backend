from typing import Protocol


class IMessagePublisher(Protocol):
    async def publish(self, queue_name: str, message: str) -> None:
        pass
