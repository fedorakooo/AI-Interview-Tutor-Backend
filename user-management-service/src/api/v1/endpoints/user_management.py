from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.api.dependencies.use_cases.user_management import (
    get_update_user_use_case,
    get_user_by_id_use_case,
    get_users_use_case,
)
from src.api.v1.models.filter import UserFilterRequest
from src.api.v1.models.user import UserResponse, UsersResponse, UserUpdateRequest
from src.application.use_cases.user_management.get_user_by_id_use_case import GetUserByIdUseCase
from src.application.use_cases.user_management.get_users_use_case import GetUsersUseCase
from src.application.use_cases.user_management.update_user_use_case import UpdateUserUseCase

router = APIRouter(prefix="", tags=["User Management"])


@router.get(
    "/user/{user_id}",
    response_model=UserResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Requesting user is blocked"},
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Unexpected server error"},
    },
)
async def get_user_by_id(
    user_id: UUID,
    user_by_id_use_case: Annotated[GetUserByIdUseCase, Depends(get_user_by_id_use_case)],
) -> UserResponse:
    user = await user_by_id_use_case(user_id=user_id)
    return UserResponse.from_dto(user)


@router.get(
    "/users",
    response_model=UsersResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Requesting user is blocked"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Unexpected server error"},
    },
)
async def get_users(
    users_use_case: Annotated[GetUsersUseCase, Depends(get_users_use_case)],
    user_filter_request: UserFilterRequest = Depends(),
) -> UsersResponse:
    user_filter = user_filter_request.to_entity()
    users_dto = await users_use_case(user_filter=user_filter)
    return UsersResponse.from_dto(users_dto)


@router.patch(
    "/user/{user_id}",
    response_model=UserResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Requesting user is blocked"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Unexpected server error"},
    },
)
async def update_user(
    user_id: UUID,
    user_update_request: UserUpdateRequest,
    user_update_use_case: Annotated[UpdateUserUseCase, Depends(get_update_user_use_case)],
) -> UserResponse:
    user_update_dto = user_update_request.to_dto()
    updated_user = await user_update_use_case(
        user_id=user_id,
        user_update_dto=user_update_dto,
    )
    return UserResponse.from_dto(updated_user)
