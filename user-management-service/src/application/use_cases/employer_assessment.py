from uuid import UUID, uuid4

from shared_models.assessment.contracts import HumanDecisionType

from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.interfaces.database.uow import IUnitOfWork
from src.infrastructure.postgres.schemas.assessment_flow import AuditLogORM


class ListCandidatesUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def __call__(self, organization_id: UUID, vacancy_id: UUID, limit: int, offset: int):
        async with self._uow:
            return await self._uow.assessment_repository.list_attempts_for_vacancy(organization_id, vacancy_id, limit, offset)


class GetAuthorizedReportUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def __call__(self, organization_id: UUID, attempt_id: UUID, actor_user_id: UUID):
        async with self._uow:
            attempt = await self._uow.assessment_repository.get_attempt_for_organization(organization_id, attempt_id)
            if attempt is None:
                raise NotFoundError("Assessment attempt not found")
            if attempt.report_reference:
                await self._uow.assessment_repository.create_audit_entry(
                    AuditLogORM(
                        id=uuid4(), actor_type="user", actor_id=actor_user_id,
                        action="assessment_report.viewed", organization_id=organization_id,
                        attempt_id=attempt_id, after={"report_available": True},
                    )
                )
            return attempt


class RecordHumanDecisionUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def __call__(self, organization_id: UUID, attempt_id: UUID, decision: HumanDecisionType, private_note: str | None, actor_user_id: UUID):
        async with self._uow:
            attempt = await self._uow.assessment_repository.get_attempt_for_organization(organization_id, attempt_id)
            if attempt is None:
                raise NotFoundError("Assessment attempt not found")
            previous = await self._uow.assessment_repository.get_decision(attempt_id)
            before = (
                {"decision": previous.decision, "private_note": previous.private_note, "version": previous.version}
                if previous is not None else None
            )
            recorded = await self._uow.assessment_repository.upsert_decision(attempt_id, decision.value, private_note, actor_user_id)
            await self._uow.assessment_repository.create_audit_entry(
                AuditLogORM(
                    id=uuid4(), actor_type="user", actor_id=actor_user_id,
                    action="human_decision.updated" if recorded.version > 1 else "human_decision.created",
                    organization_id=organization_id, attempt_id=attempt_id,
                    before=before,
                    after={"decision": recorded.decision, "private_note": recorded.private_note, "version": recorded.version},
                )
            )
            return recorded


class ListHumanDecisionHistoryUseCase:
    def __init__(self, uow: IUnitOfWork):
        self._uow = uow

    async def __call__(self, organization_id: UUID, attempt_id: UUID):
        async with self._uow:
            attempt = await self._uow.assessment_repository.get_attempt_for_organization(organization_id, attempt_id)
            if attempt is None:
                raise NotFoundError("Assessment attempt not found")
            return await self._uow.assessment_repository.list_decision_history(attempt_id)
