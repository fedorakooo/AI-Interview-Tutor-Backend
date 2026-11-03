from typing import Protocol, runtime_checkable


@runtime_checkable
class IndexedRepository(Protocol):
    async def ensure_indexes(self) -> None: ...
