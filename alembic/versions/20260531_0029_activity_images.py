"""activity cover images + media audit

Revision ID: 20260531_0029
Revises: 20260530_0028
Create Date: 2026-05-31

"""

from alembic import op
import sqlalchemy as sa

revision = "20260531_0029"
down_revision = "20260530_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("activities", sa.Column("cover_image_url", sa.String(length=512), nullable=True))
    op.add_column("activities", sa.Column("images", sa.JSON(), nullable=True))
    op.add_column(
        "activities",
        sa.Column("images_audit_status", sa.String(length=16), server_default="none", nullable=False),
    )
    op.add_column(
        "activities",
        sa.Column("images_audit_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_activities_images_audit_status", "activities", ["images_audit_status"])

    op.create_table(
        "activity_media_audits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("image_urls", sa.JSON(), nullable=False),
        sa.Column("trace_entries", sa.JSON(), nullable=True),
        sa.Column("reject_index", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_activity_media_audits_activity_id", "activity_media_audits", ["activity_id"])
    op.create_index("ix_activity_media_audits_status", "activity_media_audits", ["status"])


def downgrade() -> None:
    op.drop_index("ix_activity_media_audits_status", table_name="activity_media_audits")
    op.drop_index("ix_activity_media_audits_activity_id", table_name="activity_media_audits")
    op.drop_table("activity_media_audits")
    op.drop_index("ix_activities_images_audit_status", table_name="activities")
    op.drop_column("activities", "images_audit_updated_at")
    op.drop_column("activities", "images_audit_status")
    op.drop_column("activities", "images")
    op.drop_column("activities", "cover_image_url")
