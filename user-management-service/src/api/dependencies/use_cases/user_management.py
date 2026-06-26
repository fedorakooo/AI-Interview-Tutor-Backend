from typing import Annotated

from fastapi import Depends

from src.api.dependencies.database import get_unit_of_work
from src.application.use_cases.current_user.delete_current_user_use_case import DeleteCurrentUserUseCase
from src.application.use_cases.user_management.get_user_by_id_use_case import GetUserByIdUseCase
from src.application.use_cases.user_management.get_users_use_case import GetUsersUseCase
from src.application.use_cases.user_management.update_user_use_case import UpdateUserUseCase
from src.domain.interfaces.database.uow import IUnitOfWork


def get_user_by_id_use_case(uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)]) -> GetUserByIdUseCase:
    return GetUserByIdUseCase(uow=uow)


def get_users_use_case(uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)]) -> GetUsersUseCase:
    return GetUsersUseCase(uow=uow)


def get_update_user_use_case(uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)]) -> UpdateUserUseCase:
    return UpdateUserUseCase(uow=uow)


def get_delete_current_user_use_case(
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
) -> DeleteCurrentUserUseCase:
    return DeleteCurrentUserUseCase(uow=uow)
