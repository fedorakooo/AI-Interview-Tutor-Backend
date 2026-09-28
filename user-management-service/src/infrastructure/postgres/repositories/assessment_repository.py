from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.interfaces.database.repositories.assessment_repository import IAssessmentRepository
from src.infrastructure.postgres.schemas.assessment_flow import CandidateAttemptORM, CandidateInvitationORM


class AssessmentPostgresRepository(IAssessmentRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_invitation(self, invitation: CandidateInvitationORM) -> CandidateInvitationORM:
        self._session.add(invitation)
        await self._session.flush()
        return invitation

    async def list_invitations(self, organization_id: UUID, vacancy_id: UUID) -> list[CandidateInvitationORM]:
        result = await self._session.execute(select(CandidateInvitationORM).where(
            CandidateInvitationORM.organization_id == organization_id,
            CandidateInvitationORM.vacancy_id == vacancy_id,
        ).order_by(CandidateInvitationORM.created_at.desc()))
        return list(result.scalars())

    async def get_invitation(self, organization_id: UUID, invitation_id: UUID) -> CandidateInvitationORM | None:
        result = await self._session.execute(select(CandidateInvitationORM).where(
            CandidateInvitationORM.id == invitation_id,
            CandidateInvitationORM.organization_id == organization_id,
        ))
        return result.scalar_one_or_none()

    async def get_invitation_by_hash_for_update(self, token_hash: str) -> CandidateInvitationORM | None:
        result = await self._session.execute(select(CandidateInvitationORM).where(
            CandidateInvitationORM.token_hash == token_hash,
        ).with_for_update())
        return result.scalar_one_or_none()

    async def create_attempt(self, attempt: CandidateAttemptORM) -> CandidateAttemptORM:
        self._session.add(attempt)
        await self._session.flush()
        return attempt

    async def get_attempt_for_invitation(self, invitation_id: UUID) -> CandidateAttemptORM | None:
        result = await self._session.execute(select(CandidateAttemptORM).where(
            CandidateAttemptORM.invitation_id == invitation_id,
        ).order_by(CandidateAttemptORM.created_at.desc()))
        return result.scalars().first()

    async def get_attempt(self, attempt_id: UUID) -> CandidateAttemptORM | None:
        result = await self._session.execute(select(CandidateAttemptORM).where(CandidateAttemptORM.id == attempt_id))
        return result.scalar_one_or_none()
