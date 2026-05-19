"""wm_pay_orders for publish payment (YunGouOS)

Revision ID: 20260519_0016
Revises: 20260518_0015
Create Date: 2026-05-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260519_0016"
down_revision: Union[str, Sequence[str], None] = "20260518_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wm_pay_orders",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("qr_id", sa.String(length=64), nullable=False),
        sa.Column("product", sa.String(length=32), nullable=False, server_default="publish"),
        sa.Column("out_trade_no", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("channel", sa.String(length=16), nullable=False, server_default="native"),
        sa.Column("pay_code_url", sa.String(length=512), nullable=True),
        sa.Column("platform_order_no", sa.String(length=64), nullable=True),
        sa.Column("charge_id", sa.String(length=64), nullable=True),
        sa.Column("money", sa.String(length=16), nullable=False, server_default="1.00"),
        sa.Column("attach", sa.String(length=256), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("out_trade_no", name="uniq_wm_pay_orders_out_trade_no"),
    )
    op.create_index("idx_wm_pay_orders_user_qr", "wm_pay_orders", ["user_id", "qr_id", "product"])
    op.create_index("idx_wm_pay_orders_status_exp", "wm_pay_orders", ["status", "expires_at"])


def downgrade() -> None:
    op.drop_index("idx_wm_pay_orders_status_exp", table_name="wm_pay_orders")
    op.drop_index("idx_wm_pay_orders_user_qr", table_name="wm_pay_orders")
    op.drop_table("wm_pay_orders")
