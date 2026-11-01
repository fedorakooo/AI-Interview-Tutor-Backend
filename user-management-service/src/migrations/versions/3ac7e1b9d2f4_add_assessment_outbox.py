"""Add a transactional outbox for assessment completion notifications.

Revision ID: 3ac7e1b9d2f4
Revises: 29c0d1e2f3a4
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "3ac7e1b9d2f4"
down_revision: Union[str, None] = "29c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assessment_outbox",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(96), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(512), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("TIMEZONE('utc', now())")),
        sa.CheckConstraint("status IN ('pending', 'dispatching', 'published')", name="ck_assessment_outbox_status"),
        sa.UniqueConstraint("event_type", "event_id", name="uq_assessment_outbox_event"),
    )
    op.create_index("ix_assessment_outbox_event_id", "assessment_outbox", ["event_id"])
    op.create_index("ix_assessment_outbox_pending", "assessment_outbox", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_assessment_outbox_pending", table_name="assessment_outbox")
    op.drop_index("ix_assessment_outbox_event_id", table_name="assessment_outbox")
    op.drop_table("assessment_outbox")
