"""place activity alerts (subscribe new activities by place)

Revision ID: 20260515_0012
Revises: 20260514_0011
Create Date: 2026-05-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260515_0012"
down_revision: Union[str, Sequence[str], None] = "20260514_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "place_activity_alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("city_code", sa.String(length=16), nullable=False),
        sa.Column("place_label", sa.String(length=128), nullable=False),
        sa.Column("category_id", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("date_range", sa.String(length=16), nullable=False, server_default="all"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_place_alerts_user", "place_activity_alerts", ["user_id"])
    op.create_index("idx_place_alerts_city", "place_activity_alerts", ["city_code"])
    op.create_index(
        "uq_place_alerts_user_city_cat_dr",
        "place_activity_alerts",
        ["user_id", "city_code", "category_id", "date_range"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_place_alerts_user_city_cat_dr", table_name="place_activity_alerts")
    op.drop_index("idx_place_alerts_city", table_name="place_activity_alerts")
    op.drop_index("idx_place_alerts_user", table_name="place_activity_alerts")
    op.drop_table("place_activity_alerts")
