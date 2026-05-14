"""city hall (virtual activity per city) columns on activities

Revision ID: 20260513_0010
Revises: 20260508_0009
Create Date: 2026-05-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260513_0010"
down_revision: Union[str, Sequence[str], None] = "20260508_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "activities",
        sa.Column(
            "activity_kind",
            sa.String(length=20),
            nullable=False,
            server_default="event",
        ),
    )
    op.add_column(
        "activities",
        sa.Column("city_hall_city_code", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "uq_activities_city_hall_city_code",
        "activities",
        ["city_hall_city_code"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_activities_city_hall_city_code", table_name="activities")
    op.drop_column("activities", "city_hall_city_code")
    op.drop_column("activities", "activity_kind")
