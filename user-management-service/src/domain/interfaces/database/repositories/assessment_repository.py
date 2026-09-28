from abc import ABC, abstractmethod
from uuid import UUID

from src.infrastructure.postgres.schemas.assessment_flow import CandidateAttemptORM, CandidateInvitationORM


class IAssessmentRepository(ABC):
    @abstractmethod
    async def create_invitation(self, invitation: CandidateInvitationORM) -> CandidateInvitationORM: ...

    @abstractmethod
    async def list_invitations(self, organization_id: UUID, vacancy_id: UUID) -> list[CandidateInvitationORM]: ...

    @abstractmethod
    async def get_invitation(self, organization_id: UUID, invitation_id: UUID) -> CandidateInvitationORM | None: ...

    @abstractmethod
    async def get_invitation_by_hash_for_update(self, token_hash: str) -> CandidateInvitationORM | None: ...

    @abstractmethod
    async def create_attempt(self, attempt: CandidateAttemptORM) -> CandidateAttemptORM: ...

    @abstractmethod
    async def get_attempt_for_invitation(self, invitation_id: UUID) -> CandidateAttemptORM | None: ...

    @abstractmethod
    async def get_attempt(self, attempt_id: UUID) -> CandidateAttemptORM | None: ...
