"""city group host P2: applications, last_active_at

Revision ID: 20260529_0027
"""

from alembic import op
import sqlalchemy as sa

revision = "20260529_0027"
down_revision = "20260528_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "city_group_hosts",
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "city_group_host_applications",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("city_code", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("application_type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("intro_text", sa.String(length=500), nullable=True),
        sa.Column("nominator_user_id", sa.BigInteger(), nullable=True),
        sa.Column("reviewer_admin_id", sa.BigInteger(), nullable=True),
        sa.Column("review_note", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_city_group_host_applications_city_status",
        "city_group_host_applications",
        ["city_code", "status"],
    )
    op.create_index(
        "ix_city_group_host_applications_user",
        "city_group_host_applications",
        ["user_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_city_group_host_applications_user", table_name="city_group_host_applications")
    op.drop_index("ix_city_group_host_applications_city_status", table_name="city_group_host_applications")
    op.drop_table("city_group_host_applications")
    op.drop_column("city_group_hosts", "last_active_at")
