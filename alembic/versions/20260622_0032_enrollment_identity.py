"""activity enrollment identity fields

Revision ID: 20260622_0032
Revises: 20260614_0031
Create Date: 2026-06-22

"""

from alembic import op
import sqlalchemy as sa

revision = "20260622_0032"
down_revision = "20260614_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "activities",
        sa.Column(
            "require_enrollment_identity",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "activity_enrollments",
        sa.Column("participant_name", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "activity_enrollments",
        sa.Column("id_card_number", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "activity_enrollments",
        sa.Column("participant_phone", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("enrollment_identity_name", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("enrollment_identity_id_card", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "enrollment_identity_id_card")
    op.drop_column("users", "enrollment_identity_name")
    op.drop_column("activity_enrollments", "participant_phone")
    op.drop_column("activity_enrollments", "id_card_number")
    op.drop_column("activity_enrollments", "participant_name")
    op.drop_column("activities", "require_enrollment_identity")
