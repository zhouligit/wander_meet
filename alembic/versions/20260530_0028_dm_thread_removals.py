"""dm thread removals (delete friend)

Revision ID: 20260530_0028
"""

from alembic import op
import sqlalchemy as sa

revision = "20260530_0028"
down_revision = "20260529_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dm_thread_removals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("thread_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "removed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["thread_id"], ["dm_threads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "thread_id", name="uniq_dm_thread_removal"),
    )
    op.create_index(
        "idx_dm_thread_removals_user", "dm_thread_removals", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("idx_dm_thread_removals_user", table_name="dm_thread_removals")
    op.drop_table("dm_thread_removals")
