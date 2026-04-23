"""add user chat read cursor table

Revision ID: 20260422_0003
Revises: 20260416_0002
Create Date: 2026-04-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260422_0003"
down_revision: Union[str, Sequence[str], None] = "20260416_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_chat_reads",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("activity_id", sa.BigInteger(), nullable=False),
        sa.Column("last_read_message_id", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "activity_id", name="uniq_user_chat_read"),
    )
    op.create_index("idx_user_chat_reads_user", "user_chat_reads", ["user_id"], unique=False)
    op.create_index(
        "idx_user_chat_reads_activity", "user_chat_reads", ["activity_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("idx_user_chat_reads_activity", table_name="user_chat_reads")
    op.drop_index("idx_user_chat_reads_user", table_name="user_chat_reads")
    op.drop_table("user_chat_reads")

