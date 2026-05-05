"""add user bio and tags for public profile

Revision ID: 20260501_0006
Revises: 20260429_0005
Create Date: 2026-05-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260501_0006"
down_revision: Union[str, Sequence[str], None] = "20260429_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("bio", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("tags", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "tags")
    op.drop_column("users", "bio")
