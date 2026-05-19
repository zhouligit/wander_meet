"""activities: ended_at redundancy for past lists

Revision ID: 20260521_0019
Revises: 20260520_0018
Create Date: 2026-05-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260521_0019"
down_revision: Union[str, Sequence[str], None] = "20260520_0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "activities",
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_activities_ended_at", "activities", ["ended_at"], unique=False)
    op.create_index(
        "idx_activities_organizer_ended",
        "activities",
        ["organizer_id", "ended_at"],
        unique=False,
    )
    # 历史数据回填：已取消/已结束用 updated_at；计划结束时间已过的 published 用 end_at
    op.execute(
        """
        UPDATE activities
        SET ended_at = COALESCE(end_at, updated_at)
        WHERE activity_status IN ('cancelled', 'ended')
          AND ended_at IS NULL
        """
    )
    op.execute(
        """
        UPDATE activities
        SET ended_at = end_at
        WHERE activity_status = 'published'
          AND end_at IS NOT NULL
          AND end_at < UTC_TIMESTAMP()
          AND ended_at IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("idx_activities_organizer_ended", table_name="activities")
    op.drop_index("idx_activities_ended_at", table_name="activities")
    op.drop_column("activities", "ended_at")
