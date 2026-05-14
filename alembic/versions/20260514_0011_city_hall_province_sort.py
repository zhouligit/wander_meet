"""city hall province + sort key for catalog

Revision ID: 20260514_0011
Revises: 20260513_0010
Create Date: 2026-05-14
"""

import hashlib
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260514_0011"
down_revision: Union[str, Sequence[str], None] = "20260513_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "activities",
        sa.Column("city_hall_province_code", sa.String(length=8), nullable=True),
    )
    op.add_column(
        "activities",
        sa.Column("city_hall_sort_key", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "idx_activities_city_hall_province",
        "activities",
        ["city_hall_province_code"],
        unique=False,
    )
    # 回填：国标 6 位及以上纯数字 -> 省码 XX0000；排序键用城市码小写（与车牌/区划序一致）
    op.execute(
        """
        UPDATE activities
        SET
          city_hall_province_code = CASE
            WHEN city_hall_city_code REGEXP '^[0-9]{4,}$' THEN CONCAT(SUBSTRING(city_hall_city_code, 1, 2), '0000')
            ELSE '990000'
          END,
          city_hall_sort_key = LOWER(city_hall_city_code)
        WHERE activity_kind = 'city_hall' AND city_hall_city_code IS NOT NULL
        """
    )
    _ph = hashlib.sha256(b"_wm_internal_city_hall_system_v1").hexdigest()
    op.execute(
        f"UPDATE users SET nickname = '系统管理员' WHERE phone_hash = '{_ph}'"
    )


def downgrade() -> None:
    op.drop_index("idx_activities_city_hall_province", table_name="activities")
    op.drop_column("activities", "city_hall_sort_key")
    op.drop_column("activities", "city_hall_province_code")
