"""Store CV uploads that belong to anonymous assessment attempts."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "29c0d1e2f3a4"
down_revision: Union[str, None] = "18b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assessment_cv_uploads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("attempt_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("correlation_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("s3_object_key", sa.String(512), nullable=False),
        sa.Column("original_filename", sa.String(255)),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("error_code", sa.String(64)), sa.Column("error_message", sa.Text()),
        sa.Column("mongo_document_id", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("TIMEZONE('utc', now())")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("TIMEZONE('utc', now())")),
        sa.ForeignKeyConstraint(["attempt_id"], ["candidate_attempts.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_assessment_cv_uploads_attempt_id", "assessment_cv_uploads", ["attempt_id"])
    op.create_index("ix_assessment_cv_uploads_correlation_id", "assessment_cv_uploads", ["correlation_id"])


def downgrade() -> None:
    op.drop_index("ix_assessment_cv_uploads_correlation_id", table_name="assessment_cv_uploads")
    op.drop_index("ix_assessment_cv_uploads_attempt_id", table_name="assessment_cv_uploads")
    op.drop_table("assessment_cv_uploads")
