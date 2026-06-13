"""users birth_date for profile gate

Revision ID: 20260614_0031
Revises: 20260613_0030
Create Date: 2026-06-14

"""

from alembic import op
import sqlalchemy as sa

revision = "20260614_0031"
down_revision = "20260613_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("birth_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "birth_date")
