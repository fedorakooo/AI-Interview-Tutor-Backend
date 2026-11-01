from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.postgres.database import Base


class NotificationPreferenceORM(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        CheckConstraint(
            "quiet_hours_start IS NULL OR quiet_hours_end IS NULL OR quiet_hours_start <> quiet_hours_end",
            name="ck_notification_preferences_quiet_hours_not_equal",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    email_product: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    email_marketing: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    email_interview_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    email_plan_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    email_weekly_digest: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    in_app: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    quiet_hours_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quiet_hours_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("TIMEZONE('utc', now())"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("TIMEZONE('utc', now())"), onupdate=text("TIMEZONE('utc', now())"))
