from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from shared_models.assessment.contracts import InvitationStatus
from shared_models.feature_flags.flags import feature_enabled

from src.api.dependencies.assessment import get_invitation_token_handler
from src.api.dependencies.auth import get_candidate_attempt_token_handler
from src.api.dependencies.database import get_unit_of_work
from src.application.use_cases.assessments import AssessmentFlowError, PublicInvitationUseCase
from src.domain.interfaces.auth.candidate_attempt_token_handler import ICandidateAttemptTokenHandler
from src.domain.interfaces.database.uow import IUnitOfWork
from src.infrastructure.auth.invitation_token_handler import InvitationTokenHandler

router = APIRouter(prefix="/api/public", tags=["Candidate assessment"])
candidate_bearer = HTTPBearer()


class InvitationPreflight(BaseModel):
    vacancy_name: str
    expires_at: str
    consent_required: bool = True


class StartAttemptRequest(BaseModel):
    email: EmailStr
    consent_version: str = Field(min_length=1, max_length=64)
    display_name: str | None = Field(default=None, max_length=160)


class StartAttemptResponse(BaseModel):
    attempt_id: UUID
    attempt_token: str
    status: str


class AttemptProgress(BaseModel):
    status: str
    cv_status: str | None = None


def _enabled() -> None:
    if not feature_enabled("EMPLOYER_ASSESSMENT_DEMO", False):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def _public_error() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation unavailable")


@router.get("/invitations/{token}", response_model=InvitationPreflight)
async def preflight_invitation(
    token: str,
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    token_handler: Annotated[InvitationTokenHandler, Depends(get_invitation_token_handler)],
) -> InvitationPreflight:
    _enabled()
    try:
        invitation = await PublicInvitationUseCase(uow, token_handler).preflight(token)
    except AssessmentFlowError as exc:
        raise _public_error() from exc
    # The public contract deliberately omits email, rubric, organization id and internal ids.
    return InvitationPreflight(vacancy_name="Assessment invitation", expires_at=invitation.expires_at.isoformat())


@router.post("/invitations/{token}/start", response_model=StartAttemptResponse)
async def start_attempt(
    token: str,
    body: StartAttemptRequest,
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
    invitation_tokens: Annotated[InvitationTokenHandler, Depends(get_invitation_token_handler)],
    attempt_tokens: Annotated[ICandidateAttemptTokenHandler, Depends(get_candidate_attempt_token_handler)],
) -> StartAttemptResponse:
    _enabled()
    try:
        attempt = await PublicInvitationUseCase(uow, invitation_tokens).start(token, str(body.email), body.display_name, body.consent_version)
    except AssessmentFlowError as exc:
        raise _public_error() from exc
    return StartAttemptResponse(attempt_id=attempt.id, attempt_token=attempt_tokens.mint(str(attempt.id)), status=attempt.status)


@router.get("/attempts/{attempt_id}", response_model=AttemptProgress)
async def get_attempt_progress(
    attempt_id: UUID,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(candidate_bearer)],
    token_handler: Annotated[ICandidateAttemptTokenHandler, Depends(get_candidate_attempt_token_handler)],
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
) -> AttemptProgress:
    _enabled()
    try:
        token_handler.verify(credentials.credentials, str(attempt_id))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid attempt token") from exc
    async with uow:
        attempt = await uow.assessment_repository.get_attempt(attempt_id)
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt unavailable")
    return AttemptProgress(status=attempt.status, cv_status="pending" if attempt.status == "created" else None)
