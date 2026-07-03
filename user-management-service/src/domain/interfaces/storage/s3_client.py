from abc import ABC, abstractmethod


class IS3Client(ABC):
    @abstractmethod
    async def put_object(self, key: str, body: bytes, content_type: str) -> None:
        pass
