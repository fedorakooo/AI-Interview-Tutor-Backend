from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import settings
from src.domain.interfaces.database.repositories.user_cv_upload_repository import IUserCVUploadRepository
from src.domain.interfaces.database.repositories.user_repository import IUserRepository
from src.domain.interfaces.database.repositories.organization_repository import IOrganizationRepository
from src.domain.interfaces.database.repositories.vacancy_repository import IVacancyRepository
from src.domain.interfaces.database.uow import IUnitOfWork
from src.infrastructure.postgres.repositories.user_cv_upload_repository import UserCVUploadPostgresRepository
from src.infrastructure.postgres.repositories.user_repository import (
    UserPostgresRepository,
)
from src.infrastructure.postgres.repositories.organization_repository import OrganizationPostgresRepository
from src.infrastructure.postgres.repositories.vacancy_repository import VacancyPostgresRepository
from src.domain.interfaces.database.repositories.assessment_repository import IAssessmentRepository
from src.infrastructure.postgres.repositories.assessment_repository import AssessmentPostgresRepository
from src.domain.interfaces.database.repositories.notification_preference_repository import INotificationPreferenceRepository
from src.infrastructure.postgres.repositories.notification_preference_repository import NotificationPreferencePostgresRepository
from src.infrastructure.postgres.uow import SqlAlchemyUnitOfWork


@lru_cache
def get_async_engine():
    return create_async_engine(
        url=settings.postgres_settings.url,
        echo=settings.sql_alchemy_settings.echo,
        pool_size=settings.sql_alchemy_settings.pool_size,
        max_overflow=settings.sql_alchemy_settings.max_overflow,
    )


@lru_cache
def get_session_factory(
    async_engine: AsyncEngine = Depends(get_async_engine),
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=async_engine,
        expire_on_commit=settings.sql_alchemy_settings.expire_on_commit,
    )


async def get_session(
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> AsyncSession:
    session = session_factory()
    try:
        yield session
    finally:
        await session.close()


def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IUserRepository:
    return UserPostgresRepository(session)


def get_user_cv_upload_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IUserCVUploadRepository:
    return UserCVUploadPostgresRepository(session)


def get_organization_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IOrganizationRepository:
    return OrganizationPostgresRepository(session)


def get_vacancy_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> IVacancyRepository:
    return VacancyPostgresRepository(session)


def get_assessment_repository(session: Annotated[AsyncSession, Depends(get_session)]) -> IAssessmentRepository:
    return AssessmentPostgresRepository(session)


def get_notification_preference_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> INotificationPreferenceRepository:
    return NotificationPreferencePostgresRepository(session)


def get_unit_of_work(
    session: Annotated[AsyncSession, Depends(get_session)],
    user_repository: Annotated[IUserRepository, Depends(get_user_repository)],
    user_cv_upload_repository: Annotated[IUserCVUploadRepository, Depends(get_user_cv_upload_repository)],
    organization_repository: Annotated[IOrganizationRepository, Depends(get_organization_repository)],
    vacancy_repository: Annotated[IVacancyRepository, Depends(get_vacancy_repository)],
    assessment_repository: Annotated[IAssessmentRepository, Depends(get_assessment_repository)],
    notification_preference_repository: Annotated[
        INotificationPreferenceRepository, Depends(get_notification_preference_repository)
    ],
) -> IUnitOfWork:
    return SqlAlchemyUnitOfWork(
        session=session,
        user_repository=user_repository,
        user_cv_upload_repository=user_cv_upload_repository,
        organization_repository=organization_repository,
        vacancy_repository=vacancy_repository,
        assessment_repository=assessment_repository,
        notification_preference_repository=notification_preference_repository,
    )
