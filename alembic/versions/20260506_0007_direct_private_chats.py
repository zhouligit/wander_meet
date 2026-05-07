"""direct private chat threads, requests, messages, read state

Revision ID: 20260506_0007
Revises: 20260501_0006
Create Date: 2026-05-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260506_0007"
down_revision: Union[str, Sequence[str], None] = "20260501_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dm_threads",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_low_id", sa.BigInteger(), nullable=False),
        sa.Column("user_high_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_low_id", "user_high_id", name="uniq_dm_threads_pair"),
    )
    op.create_index("idx_dm_threads_low", "dm_threads", ["user_low_id"], unique=False)
    op.create_index("idx_dm_threads_high", "dm_threads", ["user_high_id"], unique=False)

    op.create_table(
        "dm_requests",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("activity_id", sa.BigInteger(), nullable=False),
        sa.Column("from_user_id", sa.BigInteger(), nullable=False),
        sa.Column("to_user_id", sa.BigInteger(), nullable=False),
        sa.Column("intro_text", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("thread_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["thread_id"], ["dm_threads.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "idx_dm_requests_to_status",
        "dm_requests",
        ["to_user_id", "status"],
        unique=False,
    )
    op.create_index(
        "idx_dm_requests_from_status",
        "dm_requests",
        ["from_user_id", "status"],
        unique=False,
    )
    op.create_index("idx_dm_requests_activity", "dm_requests", ["activity_id"], unique=False)

    op.create_table(
        "direct_messages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("thread_id", sa.BigInteger(), nullable=False),
        sa.Column("sender_id", sa.BigInteger(), nullable=False),
        sa.Column("msg_type", sa.String(length=16), nullable=False, server_default="text"),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["thread_id"], ["dm_threads.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_direct_messages_thread_created",
        "direct_messages",
        ["thread_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_direct_messages_thread_id_id",
        "direct_messages",
        ["thread_id", "id"],
        unique=False,
    )

    op.create_table(
        "dm_thread_reads",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("thread_id", sa.BigInteger(), nullable=False),
        sa.Column("last_read_message_id", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "thread_id", name="uniq_dm_thread_read"),
        sa.ForeignKeyConstraint(["thread_id"], ["dm_threads.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_dm_thread_reads_user", "dm_thread_reads", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_dm_thread_reads_user", table_name="dm_thread_reads")
    op.drop_table("dm_thread_reads")
    op.drop_index("idx_direct_messages_thread_id_id", table_name="direct_messages")
    op.drop_index("idx_direct_messages_thread_created", table_name="direct_messages")
    op.drop_table("direct_messages")
    op.drop_index("idx_dm_requests_activity", table_name="dm_requests")
    op.drop_index("idx_dm_requests_from_status", table_name="dm_requests")
    op.drop_index("idx_dm_requests_to_status", table_name="dm_requests")
    op.drop_table("dm_requests")
    op.drop_index("idx_dm_threads_high", table_name="dm_threads")
    op.drop_index("idx_dm_threads_low", table_name="dm_threads")
    op.drop_table("dm_threads")
