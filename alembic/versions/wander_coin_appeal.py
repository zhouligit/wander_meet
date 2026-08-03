"""add wander coin and appeal tables

Revision ID: wander_coin_appeal
Revises: 20260723_0033_add_trust_level_system
Create Date: 2026-07-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'wander_coin_appeal'
down_revision: Union[str, None] = '20260723_0033'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # 晃晃币钱包表
    op.create_table(
        'wander_coin_wallets',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False, comment='用户ID'),
        sa.Column('balance', sa.BigInteger(), nullable=False, server_default='0', comment='当前余额'),
        sa.Column('total_earned', sa.BigInteger(), nullable=False, server_default='0', comment='累计获得'),
        sa.Column('total_spent', sa.BigInteger(), nullable=False, server_default='0', comment='累计消费'),
        sa.Column('frozen_amount', sa.BigInteger(), nullable=False, server_default='0', comment='冻结金额'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index('idx_wander_coin_wallets_user_id', 'wander_coin_wallets', ['user_id'])
    
    # 晃晃币交易流水表
    op.create_table(
        'wander_coin_transactions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False, comment='用户ID'),
        sa.Column('amount', sa.BigInteger(), nullable=False, comment='变动金额'),
        sa.Column('balance_after', sa.BigInteger(), nullable=False, comment='交易后余额'),
        sa.Column('tx_type', sa.String(32), nullable=False, comment='交易类型'),
        sa.Column('ref_type', sa.String(32), nullable=True, comment='关联业务类型'),
        sa.Column('ref_id', sa.BigInteger(), nullable=True, comment='关联业务ID'),
        sa.Column('remark', sa.String(255), nullable=True, comment='备注'),
        sa.Column('expire_at', sa.DateTime(timezone=True), nullable=True, comment='过期时间'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_wander_coin_tx_user_time', 'wander_coin_transactions', ['user_id', 'created_at'])
    op.create_index('idx_wander_coin_tx_type', 'wander_coin_transactions', ['tx_type', 'created_at'])
    op.create_index('idx_wander_coin_tx_expire', 'wander_coin_transactions', ['expire_at'])
    
    # 信誉分申诉表
    op.create_table(
        'trust_score_appeals',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False, comment='申诉用户ID'),
        sa.Column('record_id', sa.BigInteger(), nullable=False, comment='关联记录ID'),
        sa.Column('appeal_reason', sa.Text(), nullable=False, comment='申诉理由'),
        sa.Column('status', sa.String(32), nullable=False, server_default='pending', comment='申诉状态'),
        sa.Column('reviewer_id', sa.BigInteger(), nullable=True, comment='审核人ID'),
        sa.Column('review_comment', sa.Text(), nullable=True, comment='审核意见'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True, comment='审核时间'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_trust_appeals_user_status', 'trust_score_appeals', ['user_id', 'status'])
    op.create_index('idx_trust_appeals_record_id', 'trust_score_appeals', ['record_id'])
    
    # 积分申诉表
    op.create_table(
        'point_appeals',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False, comment='申诉用户ID'),
        sa.Column('record_id', sa.BigInteger(), nullable=False, comment='关联记录ID'),
        sa.Column('appeal_reason', sa.Text(), nullable=False, comment='申诉理由'),
        sa.Column('status', sa.String(32), nullable=False, server_default='pending', comment='申诉状态'),
        sa.Column('reviewer_id', sa.BigInteger(), nullable=True, comment='审核人ID'),
        sa.Column('review_comment', sa.Text(), nullable=True, comment='审核意见'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True, comment='审核时间'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_point_appeals_user_status', 'point_appeals', ['user_id', 'status'])
    op.create_index('idx_point_appeals_record_id', 'point_appeals', ['record_id'])


def downgrade():
    op.drop_index('idx_point_appeals_record_id', table_name='point_appeals')
    op.drop_index('idx_point_appeals_user_status', table_name='point_appeals')
    op.drop_table('point_appeals')
    
    op.drop_index('idx_trust_appeals_record_id', table_name='trust_score_appeals')
    op.drop_index('idx_trust_appeals_user_status', table_name='trust_score_appeals')
    op.drop_table('trust_score_appeals')
    
    op.drop_index('idx_wander_coin_tx_expire', table_name='wander_coin_transactions')
    op.drop_index('idx_wander_coin_tx_type', table_name='wander_coin_transactions')
    op.drop_index('idx_wander_coin_tx_user_time', table_name='wander_coin_transactions')
    op.drop_table('wander_coin_transactions')
    
    op.drop_index('idx_wander_coin_wallets_user_id', table_name='wander_coin_wallets')
    op.drop_table('wander_coin_wallets')
