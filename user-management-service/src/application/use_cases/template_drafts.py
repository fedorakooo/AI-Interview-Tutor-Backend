from uuid import UUID, uuid4

from pydantic import ValidationError
from shared_models.assessment import AssessmentTemplateSnapshot, TemplateDraftRequest

from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.interfaces.reports.interview_spec_client import IInterviewSpecClient
from src.infrastructure.postgres.schemas.assessment_flow import AuditLogORM


class InvalidDraftRequestError(Exception):
    pass


class GenerateTemplateDraftUseCase:
    def __init__(self, uow: IUnitOfWork, spec_client: IInterviewSpecClient):
        self._uow = uow
        self._spec_client = spec_client

    async def __call__(
        self,
        organization_id: UUID,
        vacancy_id: UUID,
        actor_user_id: UUID,
        brief: str,
        language: str | None,
        cv_policy,
        candidate_feedback: bool,
    ) -> AssessmentTemplateSnapshot:
        async with self._uow:
            vacancy = await self._uow.vacancy_repository.get_by_id_and_organization_id(vacancy_id, organization_id)
            if vacancy is None:
                raise NotFoundError("Vacancy not found")
            try:
                request = TemplateDraftRequest(
                    brief=brief,
                    job_description=vacancy.job_description or None,
                    title=vacancy.title,
                    seniority=vacancy.seniority,
                    language=language or vacancy.language,
                    cv_policy=cv_policy,
                    candidate_feedback=candidate_feedback,
                )
            except ValidationError as exc:
                raise InvalidDraftRequestError() from exc
        draft = await self._spec_client.create_template_draft(request)
        async with self._uow:
            await self._uow.assessment_repository.create_audit_entry(
                AuditLogORM(
                    id=uuid4(),
                    actor_type="user",
                    actor_id=actor_user_id,
                    action="template.draft_generated",
                    organization_id=organization_id,
                    vacancy_id=vacancy_id,
                    after={"focus_areas": len(draft.criteria)},
                )
            )
        return draft
