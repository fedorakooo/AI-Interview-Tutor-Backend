"""Persist notification preferences instead of keeping them in web-process memory."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "4bd6e7f8a9b0"
down_revision: Union[str, None] = "3ac7e1b9d2f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("email_product", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("email_marketing", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("email_interview_complete", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("email_plan_ready", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("email_weekly_digest", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("in_app", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("quiet_hours_start", sa.Integer(), nullable=True),
        sa.Column("quiet_hours_end", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("TIMEZONE('utc', now())")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("TIMEZONE('utc', now())")),
        sa.CheckConstraint("quiet_hours_start IS NULL OR quiet_hours_end IS NULL OR quiet_hours_start <> quiet_hours_end", name="ck_notification_preferences_quiet_hours_not_equal"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("notification_preferences")
