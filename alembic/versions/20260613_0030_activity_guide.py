"""activity guide sections (活动说明页)

Revision ID: 20260613_0030
Revises: 20260531_0029
Create Date: 2026-06-13

"""

from alembic import op
import sqlalchemy as sa

revision = "20260613_0030"
down_revision = "20260531_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("activities", sa.Column("guide_sections", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("activities", "guide_sections")
