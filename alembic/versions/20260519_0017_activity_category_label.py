"""activities.category_label for category_id=other custom theme"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260519_0017"
down_revision: Union[str, None] = "20260519_0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "activities",
        sa.Column("category_label", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("activities", "category_label")
