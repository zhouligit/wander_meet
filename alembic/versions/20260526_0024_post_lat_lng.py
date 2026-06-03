"""posts: optional lat/lng for feed location

Revision ID: 20260526_0024
Revises: 20260525_0023
"""

from alembic import op
import sqlalchemy as sa

revision = "20260526_0024"
down_revision = "20260525_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("lat", sa.Numeric(10, 7), nullable=True))
    op.add_column("posts", sa.Column("lng", sa.Numeric(10, 7), nullable=True))


def downgrade() -> None:
    op.drop_column("posts", "lng")
    op.drop_column("posts", "lat")
