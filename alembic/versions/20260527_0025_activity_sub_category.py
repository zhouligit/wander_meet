"""activities.sub_category_id for L2 category (e.g. sports + basketball)

Revision ID: 20260527_0025
"""

from alembic import op
import sqlalchemy as sa

revision = "20260527_0025"
down_revision = "20260526_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "activities",
        sa.Column("sub_category_id", sa.String(length=32), nullable=True),
    )
    op.create_index("ix_activities_sub_category_id", "activities", ["sub_category_id"])


def downgrade() -> None:
    op.drop_index("ix_activities_sub_category_id", table_name="activities")
    op.drop_column("activities", "sub_category_id")
