"""add performance indexes for high traffic endpoints

Revision ID: 20260429_0004
Revises: 20260422_0003
Create Date: 2026-04-29
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260429_0004"
down_revision: Union[str, Sequence[str], None] = "20260422_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_activities_city_status_start",
        "activities",
        ["city_code", "activity_status", "start_at"],
        unique=False,
    )
    op.create_index(
        "idx_activities_city_status_updated",
        "activities",
        ["city_code", "activity_status", "updated_at"],
        unique=False,
    )
    op.create_index(
        "idx_activities_lat_lng",
        "activities",
        ["lat", "lng"],
        unique=False,
    )

    op.create_index(
        "idx_activity_enrollments_user_status_activity",
        "activity_enrollments",
        ["user_id", "status", "activity_id"],
        unique=False,
    )

    op.create_index(
        "idx_activity_messages_activity_id_id",
        "activity_messages",
        ["activity_id", "id"],
        unique=False,
    )

    op.create_index(
        "idx_notifications_user_read_id",
        "notifications",
        ["user_id", "read_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_notifications_user_read_id", table_name="notifications")
    op.drop_index("idx_activity_messages_activity_id_id", table_name="activity_messages")
    op.drop_index(
        "idx_activity_enrollments_user_status_activity",
        table_name="activity_enrollments",
    )
    op.drop_index("idx_activities_lat_lng", table_name="activities")
    op.drop_index("idx_activities_city_status_updated", table_name="activities")
    op.drop_index("idx_activities_city_status_start", table_name="activities")

