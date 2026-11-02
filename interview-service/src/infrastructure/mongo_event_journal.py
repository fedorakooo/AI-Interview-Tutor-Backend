from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError
from shared_models.assessment import SessionEvent, SessionEventAdapter

from src.domain.exceptions.session_errors import EventSeqConflictError
from src.domain.interfaces.event_journal import IEventJournal


class MongoEventJournal(IEventJournal):
    def __init__(self, collection: AsyncIOMotorCollection) -> None:
        self._collection = collection

    async def ensure_indexes(self) -> None:
        await self._collection.create_index([("session_id", ASCENDING), ("seq", ASCENDING)], unique=True)
        await self._collection.create_index("event_id", unique=True)

    async def append(self, event: SessionEvent) -> None:
        document = event.model_dump(mode="json")
        document["created_at"] = event.occurred_at
        try:
            await self._collection.insert_one(document)
        except DuplicateKeyError as exc:
            raise EventSeqConflictError() from exc

    async def list_events(self, session_id: str) -> list[SessionEvent]:
        cursor = self._collection.find({"session_id": session_id}, {"_id": 0, "created_at": 0}).sort("seq", ASCENDING)
        return [SessionEventAdapter.validate_python(document) for document in await cursor.to_list(length=None)]
