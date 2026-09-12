from __future__ import annotations

import json
import logging
from uuid import UUID

from jwt_handler.value_objects import AccessTokenPayload

from src.domain.exceptions.not_found_error import NotFoundError
from src.domain.interfaces.database.uow import IUnitOfWork
from src.domain.interfaces.redis.redis_client import IRedisClient

logger = logging.getLogger(__name__)


class DeleteCurrentUserUseCase:
    """GDPR-oriented account deletion: revoke sessions, remove CV objects, delete user row."""

    def __init__(
        self,
        uow: IUnitOfWork,
        redis_client: IRedisClient | None = None,
        s3_client=None,
        data_cleanup_producer=None,
    ):
        self.uow = uow
        self.redis_client = redis_client
        self.s3_client = s3_client
        self.data_cleanup_producer = data_cleanup_producer

    async def __call__(self, access_token: AccessTokenPayload) -> None:
        user_id = UUID(access_token["id"])

        async with self.uow:
            uploads = []
            if hasattr(self.uow, "user_cv_upload_repository"):
                try:
                    uploads = await self.uow.user_cv_upload_repository.list_by_user_id(user_id)
                except Exception:
                    logger.exception("Failed listing CV uploads for user %s", user_id)

            result = await self.uow.user_repository.delete(user_id)

        if not result:
            raise NotFoundError(f"User with ID {user_id} not found")

        if self.s3_client is not None:
            for upload in uploads or []:
                key = getattr(upload, "s3_object_key", None)
                if key:
                    try:
                        await self.s3_client.delete_object(key)
                    except Exception:
                        logger.exception("Failed deleting S3 object %s for user %s", key, user_id)

        if self.redis_client is not None:
            try:
                await self.redis_client.setex(
                    key=f"deleted-user:{user_id}",
                    value="1",
                    time=60 * 60 * 24 * 14,
                )
            except Exception:
                logger.exception("Failed writing deleted-user marker for %s", user_id)

        if self.data_cleanup_producer is not None:
            try:
                await self.data_cleanup_producer.send_message(
                    json.dumps({"user_id": str(user_id), "event": "user_deleted"})
                )
            except Exception:
                logger.exception("Failed publishing user_deleted cleanup event for %s", user_id)
