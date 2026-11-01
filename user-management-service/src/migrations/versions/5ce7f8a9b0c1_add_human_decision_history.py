"""Add append-only employer decision history."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "5ce7f8a9b0c1"
down_revision: Union[str, None] = "4bd6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "human_decision_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=24), nullable=False),
        sa.Column("private_note", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("TIMEZONE('utc', now())")),
        sa.CheckConstraint("decision IN ('advance', 'hold', 'reject', 'needs_review')", name="ck_human_decision_history_decision"),
        sa.ForeignKeyConstraint(["attempt_id"], ["candidate_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id", "version", name="uq_human_decision_history_attempt_version"),
    )
    op.create_index("ix_human_decision_history_attempt_created", "human_decision_history", ["attempt_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_human_decision_history_attempt_created", table_name="human_decision_history")
    op.drop_table("human_decision_history")
