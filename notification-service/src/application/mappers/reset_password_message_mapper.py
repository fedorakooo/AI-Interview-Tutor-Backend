from dataclasses import asdict
from datetime import datetime
from uuid import UUID

from src.domain.entities.reset_password_message import ResetPasswordMessage


class ResetPasswordMessageMapper:
    """Mapper for converting between Dictionary and Entity."""

    @staticmethod
    def from_dict_to_entity(data: dict) -> ResetPasswordMessage:
        return ResetPasswordMessage(
            id=str(data["id"]),
            user_id=UUID(data["user_id"]),
            email_address=data["email_address"],
            subject=data["subject"],
            body=data["body"],
            published_at=datetime.strptime(data["published_at"], "%Y-%m-%dT%H:%M:%S"),
            sent_at=None,
        )

    @staticmethod
    def from_entity_to_dict(reset_password_message: ResetPasswordMessage) -> dict:
        return asdict(reset_password_message)
