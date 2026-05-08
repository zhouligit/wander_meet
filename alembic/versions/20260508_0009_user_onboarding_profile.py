"""user profile onboarding fields

Revision ID: 20260508_0009
Revises: 20260506_0008
Create Date: 2026-05-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260508_0009"
down_revision: Union[str, Sequence[str], None] = "20260506_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("country_code", sa.String(length=8), nullable=True))
    op.add_column("users", sa.Column("traveler_roles", sa.JSON(), nullable=True))
    op.add_column("users", sa.Column("current_place", sa.String(length=256), nullable=True))
    op.add_column("users", sa.Column("stay_kind", sa.String(length=32), nullable=True))
    op.add_column(
        "users",
        sa.Column("stay_end_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("users", sa.Column("acquisition_source", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("notify_prefs", sa.JSON(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "show_distance",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.add_column(
        "users",
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # 已有用户视为已完成引导，避免强制再走一遍
    op.execute(
        sa.text(
            "UPDATE users SET onboarding_completed_at = COALESCE(updated_at, created_at) "
            "WHERE onboarding_completed_at IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("users", "onboarding_completed_at")
    op.drop_column("users", "show_distance")
    op.drop_column("users", "notify_prefs")
    op.drop_column("users", "acquisition_source")
    op.drop_column("users", "stay_end_at")
    op.drop_column("users", "stay_kind")
    op.drop_column("users", "current_place")
    op.drop_column("users", "traveler_roles")
    op.drop_column("users", "country_code")
