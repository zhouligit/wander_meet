"""wechat mini program login (mp_openid)

Revision ID: 20260517_0014
Revises: 20260516_0013
Create Date: 2026-05-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260517_0014"
down_revision: Union[str, Sequence[str], None] = "20260516_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("mp_openid", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("mp_unionid", sa.String(length=64), nullable=True))
    op.create_index("uniq_users_mp_openid", "users", ["mp_openid"], unique=True)
    op.create_index("idx_users_mp_unionid", "users", ["mp_unionid"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_users_mp_unionid", table_name="users")
    op.drop_index("uniq_users_mp_openid", table_name="users")
    op.drop_column("users", "mp_unionid")
    op.drop_column("users", "mp_openid")
