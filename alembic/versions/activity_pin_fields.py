"""add activity pin fields

Revision ID: activity_pin_fields
Revises: wander_coin_appeal
Create Date: 2026-07-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'activity_pin_fields'
down_revision: Union[str, None] = 'wander_coin_appeal'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column('activities', sa.Column('is_pinned', sa.Boolean(), nullable=False, server_default='0', comment='是否置顶'))
    op.add_column('activities', sa.Column('pinned_until', sa.DateTime(timezone=True), nullable=True, comment='置顶截止时间'))
    op.create_index('idx_activities_is_pinned', 'activities', ['is_pinned'])


def downgrade():
    op.drop_index('idx_activities_is_pinned', table_name='activities')
    op.drop_column('activities', 'pinned_until')
    op.drop_column('activities', 'is_pinned')
