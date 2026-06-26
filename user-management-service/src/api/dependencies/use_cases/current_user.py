from typing import Annotated

from fastapi import Depends

from src.api.dependencies.database import get_unit_of_work
from src.application.use_cases.current_user.delete_current_user_use_case import DeleteCurrentUserUseCase
from src.application.use_cases.current_user.get_current_user_use_case import GetCurrentUserUseCase
from src.application.use_cases.current_user.update_current_user_use_case import UpdateCurrentUserUseCase
from src.domain.interfaces.database.uow import IUnitOfWork


def get_current_user_use_case(uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)]) -> GetCurrentUserUseCase:
    return GetCurrentUserUseCase(
        uow=uow,
    )


def get_update_current_user_use_case(
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
) -> UpdateCurrentUserUseCase:
    return UpdateCurrentUserUseCase(
        uow=uow,
    )


def get_delete_current_user_use_case(
    uow: Annotated[IUnitOfWork, Depends(get_unit_of_work)],
) -> DeleteCurrentUserUseCase:
    return DeleteCurrentUserUseCase(
        uow=uow,
    )
