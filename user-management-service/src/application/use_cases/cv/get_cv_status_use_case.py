from uuid import UUID

from src.domain.entities.user_cv_upload import UserCVUpload
from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.interfaces.database.uow import IUnitOfWork


class GetCVStatusUseCase:
    def __init__(self, uow: IUnitOfWork):
        self.uow = uow

    async def __call__(self, user_id: UUID, correlation_id: UUID | None = None) -> UserCVUpload:
        async with self.uow:
            if correlation_id is not None:
                upload = await self.uow.user_cv_upload_repository.get_by_user_and_correlation_id(
                    user_id=user_id,
                    correlation_id=correlation_id,
                )
            else:
                upload = await self.uow.user_cv_upload_repository.get_latest_by_user_id(user_id)

        if upload is None:
            raise NotFoundError("No CV upload found for user")

        return upload
