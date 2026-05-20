"""wm_pay_orders.pay_provider (wechat | yungou)

Revision ID: 20260522_0020
Revises: 20260521_0019
Create Date: 2026-05-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260522_0020"
down_revision: Union[str, Sequence[str], None] = "20260521_0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "wm_pay_orders",
        sa.Column("pay_provider", sa.String(length=16), nullable=False, server_default="wechat"),
    )


def downgrade() -> None:
    op.drop_column("wm_pay_orders", "pay_provider")
