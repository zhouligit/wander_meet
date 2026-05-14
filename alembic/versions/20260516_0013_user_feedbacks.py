"""user feedbacks (suggestions & bug reports)

Revision ID: 20260516_0013
Revises: 20260515_0012
Create Date: 2026-05-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260516_0013"
down_revision: Union[str, Sequence[str], None] = "20260515_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_feedbacks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("scene", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("expectation", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("contact_willing", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("contact_note", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("platform", sa.String(length=16), nullable=False, server_default="mp-weixin"),
        sa.Column("app_version", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_user_feedbacks_user", "user_feedbacks", ["user_id"])
    op.create_index("idx_user_feedbacks_scene", "user_feedbacks", ["scene"])
    op.create_index("idx_user_feedbacks_status", "user_feedbacks", ["status"])
    op.create_index("idx_user_feedbacks_created", "user_feedbacks", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_user_feedbacks_created", table_name="user_feedbacks")
    op.drop_index("idx_user_feedbacks_status", table_name="user_feedbacks")
    op.drop_index("idx_user_feedbacks_scene", table_name="user_feedbacks")
    op.drop_index("idx_user_feedbacks_user", table_name="user_feedbacks")
    op.drop_table("user_feedbacks")
