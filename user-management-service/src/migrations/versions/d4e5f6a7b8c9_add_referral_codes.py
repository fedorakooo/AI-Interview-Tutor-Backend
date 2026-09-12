"""Add referral codes table."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "referral_codes",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("redemptions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("TIMEZONE('utc', now())"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_index("idx_referral_codes_owner", "referral_codes", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index("idx_referral_codes_owner", table_name="referral_codes")
    op.drop_table("referral_codes")
