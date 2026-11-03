import asyncio
import logging
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.api.dependencies.assessment import get_interview_data_eraser
from src.api.dependencies.s3 import get_s3_client
from src.application.use_cases.data_erasure import PurgeExpiredAssessmentDataUseCase
from src.config import settings
from src.infrastructure.postgres.repositories.assessment_repository import AssessmentPostgresRepository
from src.infrastructure.postgres.repositories.notification_preference_repository import (
    NotificationPreferencePostgresRepository,
)
from src.infrastructure.postgres.repositories.organization_repository import OrganizationPostgresRepository
from src.infrastructure.postgres.repositories.user_cv_upload_repository import UserCVUploadPostgresRepository
from src.infrastructure.postgres.repositories.user_repository import UserPostgresRepository
from src.infrastructure.postgres.repositories.vacancy_repository import VacancyPostgresRepository
from src.infrastructure.postgres.uow import SqlAlchemyUnitOfWork


class AssessmentRetentionJob:
    """Periodically erase assessment data that outlived the organization retention period."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self._task: asyncio.Task | None = None
        self._engine = create_async_engine(settings.postgres_settings.url)
        self._session_factory = async_sessionmaker(bind=self._engine, expire_on_commit=False)

    @asynccontextmanager
    async def _uow(self):
        async with self._session_factory() as session:
            yield SqlAlchemyUnitOfWork(
                session=session,
                user_repository=UserPostgresRepository(session),
                user_cv_upload_repository=UserCVUploadPostgresRepository(session),
                organization_repository=OrganizationPostgresRepository(session),
                vacancy_repository=VacancyPostgresRepository(session),
                assessment_repository=AssessmentPostgresRepository(session),
                notification_preference_repository=NotificationPreferencePostgresRepository(session),
            )

    async def start(self) -> None:
        if settings.assessment_settings.retention_job_enabled:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._engine.dispose()

    async def run_once(self) -> int:
        purge = PurgeExpiredAssessmentDataUseCase(
            self._uow, get_interview_data_eraser(), get_s3_client(), self.logger
        )
        return await purge(settings.assessment_settings.retention_batch_size)

    async def _run(self) -> None:
        while True:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger.exception("Assessment retention run failed")
            await asyncio.sleep(settings.assessment_settings.retention_job_interval_seconds)
