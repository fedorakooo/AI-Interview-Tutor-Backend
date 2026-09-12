from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, status
from jwt_handler.models import TokenResponse
from jwt_handler.value_objects import AccessTokenPayload
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.database import get_session
from src.api.dependencies.use_cases.auth import (
    get_confirm_email_verification_use_case,
    get_confirm_reset_password_use_case,
    get_login_user_use_case,
    get_logout_use_case,
    get_refresh_token_use_case,
    get_request_email_verification_use_case,
    get_request_reset_password_use_case,
    get_setup_mfa_use_case,
    get_user_registration_use_case,
    get_verify_mfa_use_case,
)
from src.api.v1.endpoints.growth import apply_referral_on_signup
from src.api.security import get_access_token_payload
from src.api.v1.models.auth import ResetPasswordRequest
from src.api.v1.models.user import UserCreateRequest, UserResponse
from src.application.use_cases.auth.confirm_reset_password_use_case import ConfirmResetPasswordUseCase
from src.application.use_cases.auth.email_verification_use_case import (
    ConfirmEmailVerificationUseCase,
    RequestEmailVerificationUseCase,
)
from src.application.use_cases.auth.logout_use_case import LogoutUseCase
from src.application.use_cases.auth.refresh_token_use_case import RefreshTokenUseCase
from src.application.use_cases.auth.request_reset_password_use_case import RequestResetPasswordUseCase
from src.application.use_cases.auth.user_login_use_case import LoginUserUseCase
from src.application.use_cases.auth.user_registration_use_case import (
    UserRegistrationUseCase,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Unique constraint violation"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Unexpected server error"},
    },
)
async def signup(
    user_create_request: UserCreateRequest,
    user_registration_use_case: Annotated[UserRegistrationUseCase, Depends(get_user_registration_use_case)],
    request_email_verification_use_case: Annotated[
        RequestEmailVerificationUseCase, Depends(get_request_email_verification_use_case)
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
    referral_code: str | None = Query(default=None, max_length=32),
) -> UserResponse:
    user_create = user_create_request.to_dto()
    created_user = await user_registration_use_case(user_create)
    if referral_code:
        try:
            await apply_referral_on_signup(session, referral_code, created_user.id)
        except Exception:
            await session.rollback()
    try:
        await request_email_verification_use_case(created_user.id)
    except Exception:
        # Signup must succeed even if verification email fails to enqueue.
        pass
    return UserResponse.from_dto(created_user)


@router.post(
    "/token",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Invalid password or login"},
        status.HTTP_403_FORBIDDEN: {"description": "User is blocked"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Unexpected server error"},
    },
)
async def token(
    login_user_use_case: Annotated[LoginUserUseCase, Depends(get_login_user_use_case)],
    username: str = Form(...),
    password: SecretStr = Form(...),
) -> TokenResponse:
    token_info = await login_user_use_case(
        username=username,
        password=password.get_secret_value(),
    )
    return TokenResponse.from_dto(token_info)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Invalid or expired refresh token"},
        status.HTTP_403_FORBIDDEN: {"description": "User is blocked"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Unexpected server error"},
    },
)
async def auth_refresh(
    refresh_token_use_case: Annotated[RefreshTokenUseCase, Depends(get_refresh_token_use_case)],
    refresh_token: str = Form(...),
) -> TokenResponse:
    token_info = await refresh_token_use_case(refresh_token)
    return TokenResponse.from_dto(token_info)


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Invalid refresh token"},
    },
)
async def logout(
    logout_use_case: Annotated[LogoutUseCase, Depends(get_logout_use_case)],
    refresh_token: str = Form(...),
) -> dict[str, str]:
    await logout_use_case(refresh_token)
    return {"detail": "Logged out successfully"}


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Unexpected server error"},
    },
)
async def request_reset_password(
    request_reset_password_use_case: Annotated[
        RequestResetPasswordUseCase, Depends(get_request_reset_password_use_case)
    ],
    email: str = Form(...),
) -> dict[str, str]:
    await request_reset_password_use_case(email)
    return {"detail": "If the account exists, a reset email has been sent"}


@router.post(
    "/reset-password/{token}",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Invalid or expired reset token"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Unexpected server error"},
    },
)
async def confirm_reset_password(
    confirm_reset_password_use_case: Annotated[
        ConfirmResetPasswordUseCase, Depends(get_confirm_reset_password_use_case)
    ],
    token: str,
    reset_password_request: ResetPasswordRequest,
) -> dict[str, str]:
    await confirm_reset_password_use_case(token, reset_password_request.new_password.get_secret_value())
    return {"detail": "Password updated successfully"}


@router.post(
    "/verify-email",
    status_code=status.HTTP_200_OK,
)
async def request_verify_email(
    access_token: Annotated[AccessTokenPayload, Depends(get_access_token_payload)],
    request_email_verification_use_case: Annotated[
        RequestEmailVerificationUseCase, Depends(get_request_email_verification_use_case)
    ],
) -> dict[str, str]:
    from uuid import UUID

    await request_email_verification_use_case(UUID(access_token["id"]))
    return {"detail": "Verification email sent"}


@router.post(
    "/verify-email/{token}",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Invalid or expired verification token"},
    },
)
async def confirm_verify_email(
    token: str,
    confirm_email_verification_use_case: Annotated[
        ConfirmEmailVerificationUseCase, Depends(get_confirm_email_verification_use_case)
    ],
) -> dict[str, str]:
    await confirm_email_verification_use_case(token)
    return {"detail": "Email verified successfully"}
