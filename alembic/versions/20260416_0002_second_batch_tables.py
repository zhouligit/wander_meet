"""second batch tables

Revision ID: 20260416_0002
Revises: 20260416_0001
Create Date: 2026-04-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260416_0002"
down_revision: Union[str, Sequence[str], None] = "20260416_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=16), nullable=False, server_default="user"),
    )

    op.create_table(
        "user_verifications",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("real_name", sa.String(length=32), nullable=True),
        sa.Column("id_card_number", sa.String(length=32), nullable=True),
        sa.Column("face_verify_token", sa.String(length=256), nullable=True),
        sa.Column("reject_reason", sa.String(length=512), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "idx_user_verifications_user_status",
        "user_verifications",
        ["user_id", "status"],
        unique=False,
    )

    op.create_table(
        "reports",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("reporter_id", sa.BigInteger(), nullable=False),
        sa.Column("target_type", sa.String(length=16), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("activity_id", sa.BigInteger(), nullable=True),
        sa.Column("reason_code", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("handled_action", sa.String(length=32), nullable=True),
        sa.Column("handler_admin_id", sa.BigInteger(), nullable=True),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_reports_status_created", "reports", ["status", "created_at"], unique=False)

    op.create_table(
        "user_blocks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("blocker_id", sa.BigInteger(), nullable=False),
        sa.Column("blocked_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("blocker_id", "blocked_id", name="uniq_user_block"),
    )
    op.create_index("idx_user_blocks_blocker", "user_blocks", ["blocker_id"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=64), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "idx_notifications_user_read_created",
        "notifications",
        ["user_id", "read_at", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_notifications_user_read_created", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("idx_user_blocks_blocker", table_name="user_blocks")
    op.drop_table("user_blocks")
    op.drop_index("idx_reports_status_created", table_name="reports")
    op.drop_table("reports")
    op.drop_index("idx_user_verifications_user_status", table_name="user_verifications")
    op.drop_table("user_verifications")
    op.drop_column("users", "role")

