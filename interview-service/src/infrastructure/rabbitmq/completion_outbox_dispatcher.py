import asyncio

from src.domain.interfaces.assessment_completed_publisher import IAssessmentCompletedPublisher
from src.domain.interfaces.completion_outbox_repository import ICompletionOutboxRepository
from src.logger import app_logger


class CompletionOutboxDispatcher:
    def __init__(
        self,
        outbox: ICompletionOutboxRepository,
        publisher: IAssessmentCompletedPublisher,
        interval_seconds: float = 30.0,
        batch_size: int = 20,
    ) -> None:
        self._outbox = outbox
        self._publisher = publisher
        self._interval_seconds = interval_seconds
        self._batch_size = batch_size
        self._task: asyncio.Task | None = None

    async def dispatch_once(self) -> int:
        published = 0
        for event in await self._outbox.list_pending(self._batch_size):
            try:
                await self._publisher.publish(event)
                await self._outbox.mark_published(event.event_id)
                published += 1
            except Exception:
                app_logger.exception("Retrying AssessmentCompleted publication failed")
        return published

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        while True:
            try:
                await self.dispatch_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                app_logger.exception("Completion outbox run failed")
            await asyncio.sleep(self._interval_seconds)
