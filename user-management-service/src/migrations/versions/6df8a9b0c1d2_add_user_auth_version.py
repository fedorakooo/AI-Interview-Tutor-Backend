"""Add account credential version for token revocation."""

import sqlalchemy as sa
from alembic import op

revision = "6df8a9b0c1d2"
down_revision = "5ce7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0"))
    # Previously enrolled MFA was not enforced during login.
    op.execute("UPDATE users SET auth_version = 1 WHERE mfa_secret IS NOT NULL")


def downgrade() -> None:
    op.drop_column("users", "auth_version")
