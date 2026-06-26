from typing import Annotated

from fastapi import APIRouter, Depends, status
from jwt_handler.value_objects import AccessTokenPayload

from src.api.dependencies.use_cases.current_user import (
    get_current_user_use_case,
    get_delete_current_user_use_case,
    get_update_current_user_use_case,
)
from src.api.security import get_access_token_payload
from src.api.v1.models.user import UserResponse, UserUpdateRequest
from src.application.use_cases.current_user.delete_current_user_use_case import DeleteCurrentUserUseCase
from src.application.use_cases.current_user.get_current_user_use_case import GetCurrentUserUseCase
from src.application.use_cases.current_user.update_current_user_use_case import UpdateCurrentUserUseCase

router = APIRouter(prefix="/user/me", tags=["Current User"])


@router.get(
    "/",
    response_model=UserResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Requesting user is blocked"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Unexpected server error"},
    },
)
async def get_me(
    access_token: Annotated[AccessTokenPayload, Depends(get_access_token_payload)],
    current_user_use_case: Annotated[GetCurrentUserUseCase, Depends(get_current_user_use_case)],
) -> UserResponse:
    current_user_dto = await current_user_use_case(access_token)
    return UserResponse.from_dto(current_user_dto)


@router.patch(
    "/",
    response_model=UserResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Requesting user is blocked"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Unexpected server error"},
    },
)
async def update_me(
    access_token: Annotated[AccessTokenPayload, Depends(get_access_token_payload)],
    user_update_request: UserUpdateRequest,
    user_update_use_case: Annotated[UpdateCurrentUserUseCase, Depends(get_update_current_user_use_case)],
) -> UserResponse:
    user_update_dto = user_update_request.to_dto()
    updated_user = await user_update_use_case(
        access_token=access_token,
        user_update_dto=user_update_dto,
    )
    return UserResponse.from_dto(updated_user)


@router.delete(
    "/",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Requesting user is blocked"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Unexpected server error"},
    },
)
async def delete_me(
    access_token: Annotated[AccessTokenPayload, Depends(get_access_token_payload)],
    delete_current_user_use_case: Annotated[DeleteCurrentUserUseCase, Depends(get_delete_current_user_use_case)],
) -> None:
    await delete_current_user_use_case(access_token)
