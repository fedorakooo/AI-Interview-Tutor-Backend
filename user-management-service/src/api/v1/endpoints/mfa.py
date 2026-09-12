"""Optional TOTP MFA scaffold for admin accounts."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from jwt_handler.value_objects import AccessTokenPayload
from pydantic import BaseModel, Field

from src.api.dependencies.use_cases.auth import get_setup_mfa_use_case, get_verify_mfa_use_case
from src.api.security import require_roles
from src.application.use_cases.auth.mfa_use_case import SetupMfaUseCase, VerifyMfaUseCase
from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.value_objects.user_role import UserRole

router = APIRouter(prefix="/auth/mfa", tags=["MFA"])


class MFASetupResponse(BaseModel):
    secret: str
    otpauth_uri: str


class MFAVerifyRequest(BaseModel):
    code: str = Field(min_length=6, max_length=8)


@router.post("/setup", response_model=MFASetupResponse)
async def mfa_setup(
    payload: Annotated[AccessTokenPayload, Depends(require_roles(UserRole.ADMIN))],
    setup_mfa_use_case: Annotated[SetupMfaUseCase, Depends(get_setup_mfa_use_case)],
) -> MFASetupResponse:
    try:
        result = await setup_mfa_use_case(UUID(payload["id"]))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return MFASetupResponse(secret=result["secret"], otpauth_uri=result["otpauth_uri"])


@router.post("/verify")
async def mfa_verify(
    body: MFAVerifyRequest,
    payload: Annotated[AccessTokenPayload, Depends(require_roles(UserRole.ADMIN))],
    verify_mfa_use_case: Annotated[VerifyMfaUseCase, Depends(get_verify_mfa_use_case)],
) -> dict[str, bool]:
    try:
        valid = await verify_mfa_use_case(UUID(payload["id"]), body.code)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code")
    return {"verified": True}
