"""user email + password auth (H5)

Revision ID: 20260518_0015
Revises: 20260517_0014
Create Date: 2026-05-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260518_0015"
down_revision: Union[str, Sequence[str], None] = "20260517_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email", sa.String(length=254), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.create_index("uniq_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("uniq_users_email", table_name="users")
    op.drop_column("users", "password_hash")
    op.drop_column("users", "email")
