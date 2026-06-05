"""city group hosts, mutes, host actions; soft-delete activity messages

Revision ID: 20260528_0026
"""

from alembic import op
import sqlalchemy as sa

revision = "20260528_0026"
down_revision = "20260527_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "city_group_hosts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("city_code", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("appointed_by", sa.BigInteger(), nullable=True),
        sa.Column("appointed_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("resigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("welcome_text", sa.String(length=500), nullable=True),
        sa.Column("announcement", sa.String(length=1000), nullable=True),
        sa.Column("announcement_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_city_group_hosts_city_code", "city_group_hosts", ["city_code"])
    op.create_index("ix_city_group_hosts_user_id", "city_group_hosts", ["user_id"])
    op.create_index(
        "ix_city_group_hosts_city_status_role",
        "city_group_hosts",
        ["city_code", "status", "role"],
    )

    op.create_table(
        "city_group_host_actions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("host_id", sa.BigInteger(), nullable=False),
        sa.Column("city_code", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("target_message_id", sa.BigInteger(), nullable=True),
        sa.Column("target_user_id", sa.BigInteger(), nullable=True),
        sa.Column("detail", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_city_group_host_actions_city_code", "city_group_host_actions", ["city_code"])
    op.create_index("ix_city_group_host_actions_host_id", "city_group_host_actions", ["host_id"])
    op.create_index("ix_city_group_host_actions_created_at", "city_group_host_actions", ["created_at"])

    op.create_table(
        "city_group_mutes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("city_code", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("muted_by_host_id", sa.BigInteger(), nullable=False),
        sa.Column("muted_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_city_group_mutes_city_user", "city_group_mutes", ["city_code", "user_id"])

    op.add_column(
        "activity_messages",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_activity_messages_deleted_at", "activity_messages", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_activity_messages_deleted_at", table_name="activity_messages")
    op.drop_column("activity_messages", "deleted_at")
    op.drop_index("ix_city_group_mutes_city_user", table_name="city_group_mutes")
    op.drop_table("city_group_mutes")
    op.drop_index("ix_city_group_host_actions_created_at", table_name="city_group_host_actions")
    op.drop_index("ix_city_group_host_actions_host_id", table_name="city_group_host_actions")
    op.drop_index("ix_city_group_host_actions_city_code", table_name="city_group_host_actions")
    op.drop_table("city_group_host_actions")
    op.drop_index("ix_city_group_hosts_city_status_role", table_name="city_group_hosts")
    op.drop_index("ix_city_group_hosts_user_id", table_name="city_group_hosts")
    op.drop_index("ix_city_group_hosts_city_code", table_name="city_group_hosts")
    op.drop_table("city_group_hosts")
