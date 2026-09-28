from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.interfaces.database.repositories.assessment_repository import IAssessmentRepository
from src.infrastructure.postgres.schemas.assessment_flow import AssessmentCVUploadORM, AuditLogORM, CandidateAttemptORM, CandidateInvitationORM, HumanDecisionORM


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

    async def create_cv_upload(self, upload: AssessmentCVUploadORM) -> AssessmentCVUploadORM:
        self._session.add(upload)
        await self._session.flush()
        return upload

    async def get_cv_upload_for_attempt(self, attempt_id: UUID) -> AssessmentCVUploadORM | None:
        result = await self._session.execute(
            select(AssessmentCVUploadORM).where(AssessmentCVUploadORM.attempt_id == attempt_id)
        )
        return result.scalar_one_or_none()

    async def get_cv_upload_by_correlation_id(self, correlation_id: UUID) -> AssessmentCVUploadORM | None:
        result = await self._session.execute(
            select(AssessmentCVUploadORM).where(AssessmentCVUploadORM.correlation_id == correlation_id)
        )
        return result.scalar_one_or_none()

    async def get_attempt_for_organization(self, organization_id: UUID, attempt_id: UUID) -> CandidateAttemptORM | None:
        result = await self._session.execute(
            select(CandidateAttemptORM)
            .join(CandidateInvitationORM, CandidateAttemptORM.invitation_id == CandidateInvitationORM.id)
            .where(CandidateAttemptORM.id == attempt_id, CandidateInvitationORM.organization_id == organization_id)
        )
        return result.scalar_one_or_none()

    async def list_attempts_for_vacancy(self, organization_id: UUID, vacancy_id: UUID, limit: int, offset: int) -> list[CandidateAttemptORM]:
        result = await self._session.execute(
            select(CandidateAttemptORM)
            .join(CandidateInvitationORM, CandidateAttemptORM.invitation_id == CandidateInvitationORM.id)
            .where(CandidateInvitationORM.organization_id == organization_id, CandidateInvitationORM.vacancy_id == vacancy_id)
            .order_by(CandidateAttemptORM.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars())

    async def get_decision(self, attempt_id: UUID) -> HumanDecisionORM | None:
        result = await self._session.execute(select(HumanDecisionORM).where(HumanDecisionORM.attempt_id == attempt_id))
        return result.scalar_one_or_none()

    async def upsert_decision(self, attempt_id: UUID, decision: str, private_note: str | None, actor_user_id: UUID) -> HumanDecisionORM:
        existing = await self.get_decision(attempt_id)
        if existing is None:
            existing = HumanDecisionORM(id=uuid4(), attempt_id=attempt_id, decision=decision, private_note=private_note, actor_user_id=actor_user_id)
            self._session.add(existing)
        else:
            existing.decision, existing.private_note, existing.actor_user_id = decision, private_note, actor_user_id
            existing.version += 1
        await self._session.flush()
        return existing

    async def create_audit_entry(self, entry: AuditLogORM) -> AuditLogORM:
        self._session.add(entry)
        await self._session.flush()
        return entry
