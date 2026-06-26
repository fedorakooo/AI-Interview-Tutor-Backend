from typing import Annotated

from fastapi import APIRouter, Depends, Form, status
from jwt_handler.models import TokenResponse
from pydantic import SecretStr

from src.api.dependencies.use_cases.auth import (
    get_confirm_reset_password_use_case,
    get_login_user_use_case,
    get_refresh_token_use_case,
    get_request_reset_password_use_case,
    get_user_registration_use_case,
)
from src.api.v1.models.auth import PasswordResetTokenResponse, ResetPasswordRequest
from src.api.v1.models.user import UserCreateRequest, UserResponse
from src.application.use_cases.auth.confirm_reset_password_use_case import ConfirmResetPasswordUseCase
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
) -> UserResponse:
    user_create = user_create_request.to_dto()
    created_user = await user_registration_use_case(user_create)
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
    "/reset-password",
    response_model=PasswordResetTokenResponse,
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
) -> PasswordResetTokenResponse:
    reset_token = await request_reset_password_use_case(email)
    return PasswordResetTokenResponse(password_reset_token=reset_token)


@router.post(
    "/reset-password/{token}",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Invalid or expired reset token"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Unexpected server error"},
    },
)
async def confirm_reset_password(
    confirm_reset_password_use_case: Annotated[ConfirmResetPasswordUseCase, Depends(get_confirm_reset_password_use_case)],
    token: str,
    reset_password_request: ResetPasswordRequest,
) -> dict[str, str]:
    await confirm_reset_password_use_case(token, reset_password_request.new_password.get_secret_value())
    return {"detail": "Password updated successfully"}
