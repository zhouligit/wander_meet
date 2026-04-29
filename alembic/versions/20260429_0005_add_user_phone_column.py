"""add plain phone column on users table

Revision ID: 20260429_0005
Revises: 20260429_0004
Create Date: 2026-04-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260429_0005"
down_revision: Union[str, Sequence[str], None] = "20260429_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(length=20), nullable=True))
    op.create_index("idx_users_phone", "users", ["phone"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_users_phone", table_name="users")
    op.drop_column("users", "phone")

