"""user dy_openid for douyin mini program login

Revision ID: 20260523_0021
Revises: 20260521_0019
Create Date: 2026-05-23

"""

from alembic import op
import sqlalchemy as sa

revision = "20260523_0021"
down_revision = "20260522_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("dy_openid", sa.String(length=64), nullable=True))
    op.create_index("uniq_users_dy_openid", "users", ["dy_openid"], unique=True)


def downgrade() -> None:
    op.drop_index("uniq_users_dy_openid", table_name="users")
    op.drop_column("users", "dy_openid")
