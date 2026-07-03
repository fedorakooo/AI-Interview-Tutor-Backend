import asyncio
import json
import logging
from uuid import UUID

import aio_pika
from shared_models.messaging.cv_analysis import CVAnalysisResultMessage
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.config import settings
from src.domain.entities.user_cv_upload import UserCVUpload
from src.infrastructure.postgres.repositories.user_cv_upload_repository import UserCVUploadPostgresRepository
from src.infrastructure.postgres.repositories.user_repository import UserPostgresRepository
from src.infrastructure.postgres.uow import SqlAlchemyUnitOfWork


class CVResultsConsumer:
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self._task: asyncio.Task | None = None
        self._engine = create_async_engine(settings.postgres_settings.url)
        self._session_factory = async_sessionmaker(bind=self._engine, expire_on_commit=False)

    async def start(self) -> None:
        self._task = asyncio.create_task(self._consume_loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._engine.dispose()

    async def _consume_loop(self) -> None:
        connection = await aio_pika.connect_robust(settings.rabbitmq_settings.url)
        async with connection:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=5)
            queue = await channel.declare_queue(
                settings.rabbitmq_settings.cv_analysis_results_queue_name,
                durable=True,
            )

            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        await self._handle_message(message.body.decode())

    async def _handle_message(self, payload: str) -> None:
        result = CVAnalysisResultMessage.model_validate_json(payload)
        async with self._session_factory() as session:
            user_repository = UserPostgresRepository(session)
            cv_repository = UserCVUploadPostgresRepository(session)
            uow = SqlAlchemyUnitOfWork(
                session=session,
                user_repository=user_repository,
                user_cv_upload_repository=cv_repository,
            )

            async with uow:
                existing = await uow.user_cv_upload_repository.get_by_correlation_id(result.correlation_id)
                if existing is None:
                    self.logger.warning(
                        "Received CV result for unknown correlation_id=%s",
                        result.correlation_id,
                    )
                    return

                updated = UserCVUpload(
                    id=existing.id,
                    user_id=existing.user_id,
                    correlation_id=existing.correlation_id,
                    s3_object_key=existing.s3_object_key,
                    status=result.status,
                    original_filename=existing.original_filename,
                    error_code=result.error_code,
                    error_message=result.error_message,
                    mongo_document_id=result.mongo_document_id,
                    created_at=existing.created_at,
                    updated_at=existing.updated_at,
                )
                await uow.user_cv_upload_repository.update(updated)
                self.logger.info(
                    "Updated CV upload status correlation_id=%s status=%s",
                    result.correlation_id,
                    result.status.value,
                )
