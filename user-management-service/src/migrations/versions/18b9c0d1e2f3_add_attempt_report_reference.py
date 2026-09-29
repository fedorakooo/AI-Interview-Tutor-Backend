"""Store the authorized reference to an assessment report.

Revision ID: 18b9c0d1e2f3
Revises: 07a8b9c0d1e2
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "18b9c0d1e2f3"
down_revision: Union[str, None] = "07a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("candidate_attempts", sa.Column("report_reference", sa.String(512), nullable=True))
    op.add_column("candidate_attempts", sa.Column("report_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("candidate_attempts", "report_version")
    op.drop_column("candidate_attempts", "report_reference")
