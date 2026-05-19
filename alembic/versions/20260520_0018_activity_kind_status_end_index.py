"""activities: composite index for list filters (kind, status, end_at, start_at)

Revision ID: 20260520_0018
Revises: 20260519_0017
Create Date: 2026-05-20
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260520_0018"
down_revision: Union[str, Sequence[str], None] = "20260519_0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_activities_kind_status_end_start",
        "activities",
        ["activity_kind", "activity_status", "end_at", "start_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_activities_kind_status_end_start", table_name="activities")
