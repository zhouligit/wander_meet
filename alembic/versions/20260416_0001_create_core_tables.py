"""create core tables

Revision ID: 20260416_0001
Revises:
Create Date: 2026-04-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260416_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("phone_hash", sa.String(length=64), nullable=False),
        sa.Column("nickname", sa.String(length=32), nullable=False),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("phone_hash", name="uniq_users_phone_hash"),
    )
    op.create_index("idx_users_phone_hash", "users", ["phone_hash"], unique=False)

    op.create_table(
        "activities",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("organizer_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category_id", sa.String(length=32), nullable=False),
        sa.Column("city_code", sa.String(length=16), nullable=False),
        sa.Column("location_name", sa.String(length=128), nullable=False),
        sa.Column("address_detail", sa.String(length=256), nullable=True),
        sa.Column("lat", sa.Numeric(10, 7), nullable=False),
        sa.Column("lng", sa.Numeric(10, 7), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_members", sa.Integer(), nullable=False),
        sa.Column("fee_type", sa.String(length=16), nullable=False, server_default="free"),
        sa.Column("fee_amount_cents", sa.Integer(), nullable=True),
        sa.Column(
            "activity_status",
            sa.String(length=24),
            nullable=False,
            server_default="published",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_activities_city_code", "activities", ["city_code"], unique=False)
    op.create_index(
        "idx_activities_status_start", "activities", ["activity_status", "start_at"], unique=False
    )

    op.create_table(
        "activity_enrollments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("activity_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="joined"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("activity_id", "user_id", name="uniq_activity_user"),
    )
    op.create_index(
        "idx_activity_enrollments_activity_status",
        "activity_enrollments",
        ["activity_id", "status"],
        unique=False,
    )

    op.create_table(
        "activity_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("activity_id", sa.BigInteger(), nullable=False),
        sa.Column("sender_id", sa.BigInteger(), nullable=False),
        sa.Column("msg_type", sa.String(length=16), nullable=False, server_default="text"),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "idx_activity_messages_activity_created",
        "activity_messages",
        ["activity_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_activity_messages_activity_created", table_name="activity_messages")
    op.drop_table("activity_messages")
    op.drop_index(
        "idx_activity_enrollments_activity_status", table_name="activity_enrollments"
    )
    op.drop_table("activity_enrollments")
    op.drop_index("idx_activities_status_start", table_name="activities")
    op.drop_index("idx_activities_city_code", table_name="activities")
    op.drop_table("activities")
    op.drop_index("idx_users_phone_hash", table_name="users")
    op.drop_table("users")

