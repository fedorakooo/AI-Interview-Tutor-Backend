from typing import Annotated
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from jwt_handler.value_objects import AccessTokenPayload
from pydantic import BaseModel, Field
from shared_models.assessment import (
    AssessmentOverview,
    FeedbackEditRequest,
    FeedbackView,
    FocusDetail,
    ReviewRequest,
)
from shared_models.assessment.contracts import AssessmentTemplateSnapshot, CvPolicy, HumanDecisionType, VacancyStatus
from shared_models.assessment.evidence import Verdict
from shared_models.feature_flags.flags import feature_enabled

from src.api.dependencies.database import get_unit_of_work
from src.api.dependencies.assessment import (
    get_interview_data_eraser,
    get_interview_feedback_client,
    get_interview_report_client,
    get_interview_spec_client,
    get_invitation_token_handler,
)
from src.api.security import require_authenticated, require_org_role
from src.application.use_cases.vacancies import (
    ActivateVacancyUseCase,
    CreateVacancyUseCase,
    GetVacancyUseCase,
    ListVacanciesUseCase,
    ReplaceTemplateUseCase,
    UpdateVacancyUseCase,
)
from src.domain.entities.organization import OrganizationMember
from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.value_objects.organization_role import OrganizationRole
from src.application.use_cases.assessments import CreateInvitationUseCase, RevokeInvitationUseCase
from src.application.use_cases.employer_assessment import GetAuthorizedReportUseCase, ListCandidatesUseCase, ListHumanDecisionHistoryUseCase, RecordHumanDecisionUseCase
from src.domain.exceptions.interview_report_errors import (
    InterviewReportNotFoundError,
    InterviewReportNotReadyError,
    InterviewReportUnavailableError,
)
from src.api.dependencies.s3 import get_s3_client
from src.application.use_cases.data_erasure import EraseAttemptDataUseCase
from src.application.use_cases.candidate_feedback import (
    ApproveCandidateFeedbackUseCase,
    FeedbackNotAvailableError,
    FeedbackVersionMismatchError,
)
from src.application.use_cases.template_drafts import GenerateTemplateDraftUseCase, InvalidDraftRequestError
from src.domain.interfaces.reports.interview_data_eraser import IInterviewDataEraser
from src.domain.interfaces.reports.interview_feedback_client import IInterviewFeedbackClient
from src.domain.interfaces.storage.s3_client import IS3Client
from src.domain.interfaces.reports.interview_report_client import IInterviewReportClient
from src.domain.interfaces.reports.interview_spec_client import IInterviewSpecClient
from src.infrastructure.auth.invitation_token_handler import InvitationTokenHandler

router = APIRouter(prefix="/organizations/{organization_id}/vacancies", tags=["Vacancies"])
assessment_router = APIRouter(prefix="/organizations/{organization_id}/attempts", tags=["Assessments"])


class VacancyCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    job_description: str = Field(min_length=1, max_length=20_000)
    seniority: str = Field(min_length=1, max_length=64)
    language: str = Field(min_length=2, max_length=16)
    template: AssessmentTemplateSnapshot


class VacancyView(BaseModel):
    id: UUID
    organization_id: UUID
    title: str
    status: VacancyStatus
    active_template_version: int | None


class VacancyUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    job_description: str | None = Field(default=None, min_length=1, max_length=20_000)
    seniority: str | None = Field(default=None, min_length=1, max_length=64)
    language: str | None = Field(default=None, min_length=2, max_length=16)


class InvitationCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class InvitationView(BaseModel):
    id: UUID
    status: str
    expires_at: datetime
    attempts_started: int


class CandidateAttemptView(BaseModel):
    id: UUID
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    report_available: bool


class ReportView(BaseModel):
    attempt_id: UUID
    status: str
    report_reference: str
    report_version: int | None


class FeedbackEditBody(BaseModel):
    text: str = Field(min_length=1, max_length=4_000)


class FeedbackApproveBody(BaseModel):
    version: int = Field(ge=1)


class FeedbackApprovalView(BaseModel):
    queued: bool


class TemplateDraftBody(BaseModel):
    brief: str = Field(min_length=1, max_length=8_000)
    language: str | None = Field(default=None, pattern=r"^[a-z]{2,3}(-[A-Za-z]{2,4})?$")
    cv_policy: CvPolicy = CvPolicy.REQUIRED
    candidate_feedback: bool = False


class FocusReviewRequest(BaseModel):
    comment: str = Field(min_length=1, max_length=2_000)
    manual_verdict: Verdict | None = None


class HumanDecisionRequest(BaseModel):
    decision: HumanDecisionType
    private_note: str | None = Field(default=None, max_length=4_000)


class HumanDecisionView(BaseModel):
    decision: HumanDecisionType
    version: int


class HumanDecisionHistoryView(HumanDecisionView):
    actor_user_id: UUID
    private_note: str | None
    created_at: datetime


def _require_feature() -> None:
    if not feature_enabled("EMPLOYER_ASSESSMENT_DEMO", False):
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Employer assessment is disabled")


@router.post("", response_model=VacancyView, status_code=status.HTTP_201_CREATED)
async def create_vacancy(
    organization_id: UUID,
    body: VacancyCreate,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[OrganizationMember, Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.RECRUITER))],
) -> VacancyView:
    _require_feature()
    vacancy = await CreateVacancyUseCase(uow)(
        organization_id=organization_id,
        actor_user_id=UUID(payload["id"]),
        title=body.title,
        job_description=body.job_description,
        seniority=body.seniority,
        language=body.language,
        snapshot=body.template,
    )
    return VacancyView.model_validate(vacancy, from_attributes=True)


@router.get("", response_model=list[VacancyView])
async def list_vacancies(
    organization_id: UUID,
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[
        OrganizationMember,
        Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.RECRUITER, OrganizationRole.HIRING_MANAGER)),
    ],
) -> list[VacancyView]:
    _require_feature()
    vacancies = await ListVacanciesUseCase(uow)(organization_id)
    return [VacancyView.model_validate(vacancy, from_attributes=True) for vacancy in vacancies]


@router.get("/{vacancy_id}", response_model=VacancyView)
async def get_vacancy(
    organization_id: UUID,
    vacancy_id: UUID,
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[
        OrganizationMember,
        Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.RECRUITER, OrganizationRole.HIRING_MANAGER)),
    ],
) -> VacancyView:
    _require_feature()
    vacancy = await GetVacancyUseCase(uow)(vacancy_id, organization_id)
    return VacancyView.model_validate(vacancy, from_attributes=True)


@router.patch("/{vacancy_id}", response_model=VacancyView)
async def update_vacancy(
    organization_id: UUID,
    vacancy_id: UUID,
    body: VacancyUpdate,
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[OrganizationMember, Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.RECRUITER))],
) -> VacancyView:
    _require_feature()
    vacancy = await UpdateVacancyUseCase(uow)(vacancy_id, organization_id, body.model_dump(exclude_none=True))
    return VacancyView.model_validate(vacancy, from_attributes=True)


@router.post("/{vacancy_id}/template/draft", response_model=AssessmentTemplateSnapshot)
async def create_template_draft(
    organization_id: UUID, vacancy_id: UUID, body: TemplateDraftBody,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    spec_client: Annotated[IInterviewSpecClient, Depends(get_interview_spec_client)],
    _: Annotated[OrganizationMember, Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.RECRUITER))],
) -> AssessmentTemplateSnapshot:
    _require_feature()
    try:
        return await GenerateTemplateDraftUseCase(uow, spec_client)(
            organization_id, vacancy_id, UUID(payload["id"]), body.brief, body.language, body.cv_policy, body.candidate_feedback
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vacancy not found") from exc
    except InvalidDraftRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Set the draft language as a code like en or ru, or fix the vacancy language",
        ) from exc
    except (InterviewReportNotFoundError, InterviewReportNotReadyError, InterviewReportUnavailableError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Draft service unavailable") from exc


@router.put("/{vacancy_id}/template", response_model=VacancyView)
async def replace_template(
    organization_id: UUID,
    vacancy_id: UUID,
    snapshot: AssessmentTemplateSnapshot,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[OrganizationMember, Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.RECRUITER))],
) -> VacancyView:
    _require_feature()
    vacancy = await ReplaceTemplateUseCase(uow)(
        vacancy_id=vacancy_id,
        organization_id=organization_id,
        actor_user_id=UUID(payload["id"]),
        snapshot=snapshot,
    )
    return VacancyView.model_validate(vacancy, from_attributes=True)


@router.post("/{vacancy_id}/activate", response_model=VacancyView)
async def activate_vacancy(
    organization_id: UUID,
    vacancy_id: UUID,
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[OrganizationMember, Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.RECRUITER))],
) -> VacancyView:
    _require_feature()
    vacancy = await ActivateVacancyUseCase(uow)(vacancy_id, organization_id)
    return VacancyView.model_validate(vacancy, from_attributes=True)


@router.post("/{vacancy_id}/invitations", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    organization_id: UUID, vacancy_id: UUID, body: InvitationCreate,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    tokens: Annotated[InvitationTokenHandler, Depends(get_invitation_token_handler)],
    _: Annotated[OrganizationMember, Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.RECRUITER))],
) -> dict:
    _require_feature()
    invitation, raw_token = await CreateInvitationUseCase(uow, tokens)(organization_id, vacancy_id, UUID(payload["id"]), body.email)
    # The raw secret exists in exactly this create response; persistence and later views have only its digest.
    return {"id": str(invitation.id), "status": invitation.status, "expires_at": invitation.expires_at.isoformat(), "invitation_token": raw_token}


@router.get("/{vacancy_id}/invitations", response_model=list[InvitationView])
async def list_invitations(
    organization_id: UUID, vacancy_id: UUID,
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[OrganizationMember, Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.RECRUITER))],
) -> list[InvitationView]:
    _require_feature()
    async with uow:
        invitations = await uow.assessment_repository.list_invitations(organization_id, vacancy_id)
    return [InvitationView(id=item.id, status=item.status, expires_at=item.expires_at, attempts_started=item.attempts_started) for item in invitations]


@router.post("/{vacancy_id}/invitations/{invitation_id}/revoke", response_model=InvitationView)
async def revoke_invitation(
    organization_id: UUID, vacancy_id: UUID, invitation_id: UUID,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[OrganizationMember, Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.RECRUITER))],
) -> InvitationView:
    _require_feature()
    invitation = await RevokeInvitationUseCase(uow)(organization_id, invitation_id, UUID(payload["id"]))
    return InvitationView(id=invitation.id, status=invitation.status, expires_at=invitation.expires_at, attempts_started=invitation.attempts_started)


@router.get("/{vacancy_id}/candidates", response_model=list[CandidateAttemptView])
async def list_candidates(
    organization_id: UUID, vacancy_id: UUID, uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[OrganizationMember, Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.RECRUITER, OrganizationRole.HIRING_MANAGER))],
    limit: int = 50, offset: int = 0,
) -> list[CandidateAttemptView]:
    _require_feature()
    attempts = await ListCandidatesUseCase(uow)(organization_id, vacancy_id, min(limit, 100), max(offset, 0))
    return [CandidateAttemptView(id=item.id, status=item.status, started_at=item.started_at, completed_at=item.completed_at, report_available=bool(item.report_reference)) for item in attempts]


@assessment_router.get("/{attempt_id}/report", response_model=ReportView)
async def get_report(
    organization_id: UUID, attempt_id: UUID, uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    _: Annotated[OrganizationMember, Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.RECRUITER, OrganizationRole.HIRING_MANAGER))],
) -> ReportView:
    _require_feature()
    attempt = await GetAuthorizedReportUseCase(uow)(organization_id, attempt_id, UUID(payload["id"]))
    if not attempt.report_reference:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report unavailable")
    return ReportView(attempt_id=attempt.id, status=attempt.status, report_reference=attempt.report_reference, report_version=attempt.report_version)


_REPORT_ROLES = (OrganizationRole.ADMIN, OrganizationRole.RECRUITER, OrganizationRole.HIRING_MANAGER)
_REPORT_ERRORS = (InterviewReportNotFoundError, InterviewReportNotReadyError, InterviewReportUnavailableError)


def _report_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, InterviewReportNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report unavailable")
    if isinstance(exc, InterviewReportNotReadyError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Report is not ready")
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Report service unavailable")


async def _authorize_report(
    uow: IUnitOfWork, organization_id: UUID, attempt_id: UUID, actor_id: UUID, action: str, details: dict
) -> None:
    attempt = await GetAuthorizedReportUseCase(uow)(organization_id, attempt_id, actor_id, action, details)
    if not attempt.report_reference:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report unavailable")


@assessment_router.get("/{attempt_id}/report/overview", response_model=AssessmentOverview)
async def get_report_overview(
    organization_id: UUID, attempt_id: UUID,
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    reports: Annotated[IInterviewReportClient, Depends(get_interview_report_client)],
    _: Annotated[OrganizationMember, Depends(require_org_role(*_REPORT_ROLES))],
) -> AssessmentOverview:
    _require_feature()
    await _authorize_report(uow, organization_id, attempt_id, UUID(payload["id"]), "assessment_report.viewed", {"view": "overview"})
    try:
        return await reports.get_overview(attempt_id)
    except _REPORT_ERRORS as exc:
        raise _report_http_error(exc) from exc


@assessment_router.get("/{attempt_id}/report/focus/{focus_id}", response_model=FocusDetail)
async def get_report_focus_detail(
    organization_id: UUID, attempt_id: UUID, focus_id: str,
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    reports: Annotated[IInterviewReportClient, Depends(get_interview_report_client)],
    _: Annotated[OrganizationMember, Depends(require_org_role(*_REPORT_ROLES))],
) -> FocusDetail:
    _require_feature()
    await _authorize_report(
        uow, organization_id, attempt_id, UUID(payload["id"]), "assessment_report.focus_viewed", {"focus_id": focus_id}
    )
    try:
        return await reports.get_focus_detail(attempt_id, focus_id)
    except _REPORT_ERRORS as exc:
        raise _report_http_error(exc) from exc


@assessment_router.post("/{attempt_id}/report/focus/{focus_id}/reviews", response_model=FocusDetail)
async def add_report_focus_review(
    organization_id: UUID, attempt_id: UUID, focus_id: str, body: FocusReviewRequest,
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    reports: Annotated[IInterviewReportClient, Depends(get_interview_report_client)],
    _: Annotated[OrganizationMember, Depends(require_org_role(*_REPORT_ROLES))],
) -> FocusDetail:
    _require_feature()
    actor_id = UUID(payload["id"])
    details = {"focus_id": focus_id, "manual_verdict": body.manual_verdict.value if body.manual_verdict else None}
    await _authorize_report(uow, organization_id, attempt_id, actor_id, "assessment_report.reviewed", details)
    try:
        return await reports.add_review(
            attempt_id, focus_id, ReviewRequest(author_id=actor_id, comment=body.comment, manual_verdict=body.manual_verdict)
        )
    except _REPORT_ERRORS as exc:
        raise _report_http_error(exc) from exc


_FEEDBACK_ROLES = (OrganizationRole.ADMIN, OrganizationRole.RECRUITER)


@assessment_router.get("/{attempt_id}/feedback", response_model=FeedbackView)
async def get_candidate_feedback(
    organization_id: UUID, attempt_id: UUID,
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    feedback: Annotated[IInterviewFeedbackClient, Depends(get_interview_feedback_client)],
    _: Annotated[OrganizationMember, Depends(require_org_role(*_FEEDBACK_ROLES))],
) -> FeedbackView:
    _require_feature()
    await _authorize_report(uow, organization_id, attempt_id, UUID(payload["id"]), "candidate_feedback.viewed", {})
    try:
        return await feedback.get_feedback(attempt_id)
    except _REPORT_ERRORS as exc:
        raise _report_http_error(exc) from exc


@assessment_router.put("/{attempt_id}/feedback", response_model=FeedbackView)
async def edit_candidate_feedback(
    organization_id: UUID, attempt_id: UUID, body: FeedbackEditBody,
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    feedback: Annotated[IInterviewFeedbackClient, Depends(get_interview_feedback_client)],
    _: Annotated[OrganizationMember, Depends(require_org_role(*_FEEDBACK_ROLES))],
) -> FeedbackView:
    _require_feature()
    actor_id = UUID(payload["id"])
    await _authorize_report(uow, organization_id, attempt_id, actor_id, "candidate_feedback.edited", {})
    try:
        return await feedback.edit_feedback(attempt_id, FeedbackEditRequest(editor_id=actor_id, text=body.text))
    except InterviewReportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate feedback unavailable") from exc
    except _REPORT_ERRORS as exc:
        raise _report_http_error(exc) from exc


@assessment_router.post("/{attempt_id}/feedback/approve", response_model=FeedbackApprovalView)
async def approve_candidate_feedback(
    organization_id: UUID, attempt_id: UUID, body: FeedbackApproveBody,
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    feedback: Annotated[IInterviewFeedbackClient, Depends(get_interview_feedback_client)],
    _: Annotated[OrganizationMember, Depends(require_org_role(*_FEEDBACK_ROLES))],
) -> FeedbackApprovalView:
    _require_feature()
    try:
        queued = await ApproveCandidateFeedbackUseCase(uow, feedback)(
            organization_id, attempt_id, UUID(payload["id"]), body.version
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found") from exc
    except FeedbackNotAvailableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Feedback is not available yet") from exc
    except FeedbackVersionMismatchError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Feedback text changed, review it again") from exc
    except _REPORT_ERRORS as exc:
        raise _report_http_error(exc) from exc
    return FeedbackApprovalView(queued=queued)


@assessment_router.delete("/{attempt_id}/data", status_code=status.HTTP_204_NO_CONTENT)
async def erase_attempt_data(
    organization_id: UUID, attempt_id: UUID,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    eraser: Annotated[IInterviewDataEraser, Depends(get_interview_data_eraser)],
    s3_client: Annotated[IS3Client, Depends(get_s3_client)],
    _: Annotated[OrganizationMember, Depends(require_org_role(OrganizationRole.ADMIN))],
) -> None:
    _require_feature()
    try:
        await EraseAttemptDataUseCase(uow, eraser, s3_client)(organization_id, attempt_id, UUID(payload["id"]), "request")
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found") from exc
    except _REPORT_ERRORS as exc:
        raise _report_http_error(exc) from exc


@assessment_router.post("/{attempt_id}/decision", response_model=HumanDecisionView)
async def record_decision(
    organization_id: UUID, attempt_id: UUID, body: HumanDecisionRequest,
    payload: Annotated[AccessTokenPayload, Depends(require_authenticated)],
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[OrganizationMember, Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.RECRUITER, OrganizationRole.HIRING_MANAGER))],
) -> HumanDecisionView:
    _require_feature()
    recorded = await RecordHumanDecisionUseCase(uow)(organization_id, attempt_id, body.decision, body.private_note, UUID(payload["id"]))
    return HumanDecisionView(decision=HumanDecisionType(recorded.decision), version=recorded.version)


@assessment_router.get("/{attempt_id}/decision-history", response_model=list[HumanDecisionHistoryView])
async def get_decision_history(
    organization_id: UUID, attempt_id: UUID,
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    _: Annotated[OrganizationMember, Depends(require_org_role(OrganizationRole.ADMIN, OrganizationRole.RECRUITER, OrganizationRole.HIRING_MANAGER))],
) -> list[HumanDecisionHistoryView]:
    _require_feature()
    history = await ListHumanDecisionHistoryUseCase(uow)(organization_id, attempt_id)
    return [
        HumanDecisionHistoryView(
            decision=HumanDecisionType(item.decision), version=item.version,
            actor_user_id=item.actor_user_id, private_note=item.private_note,
            created_at=item.created_at,
        )
        for item in history
    ]
