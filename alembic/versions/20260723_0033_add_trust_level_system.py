"""add trust level system

Revision ID: 20260723_0033
Revises: 20260622_0032
Create Date: 2026-07-23

"""
from alembic import op
import sqlalchemy as sa


revision = "20260723_0033"
down_revision = "20260622_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建信誉分变动记录表
    op.create_table(
        "trust_score_record",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("change", sa.Integer(), nullable=False, comment="变动值"),
        sa.Column("trust_score_before", sa.Integer(), nullable=False, comment="变动前分数"),
        sa.Column("trust_score_after", sa.Integer(), nullable=False, comment="变动后分数"),
        sa.Column("reason", sa.String(64), nullable=False, comment="变动原因"),
        sa.Column("reason_detail", sa.String(255), nullable=True, comment="详细说明"),
        sa.Column("ref_type", sa.String(32), nullable=True, comment="关联业务类型"),
        sa.Column("ref_id", sa.Integer(), nullable=True, comment="关联业务ID"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trust_score_record_user_id", "trust_score_record", ["user_id"])
    op.create_index(
        "ix_trust_score_record_user_created",
        "trust_score_record",
        ["user_id", "created_at"],
    )

    # 创建用户等级表
    op.create_table(
        "user_levels",
        sa.Column("user_id", sa.Integer(), primary_key=True),
        sa.Column("total_points", sa.Integer(), nullable=False, default=0, comment="总积分"),
        sa.Column("level_code", sa.String(32), nullable=False, default="recruit", comment="等级代码"),
        sa.Column("level_name", sa.String(64), nullable=False, default="新兵", comment="等级名称"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_user_levels_total_points", "user_levels", ["total_points"])

    # 创建积分变动记录表
    op.create_table(
        "point_record",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False, comment="变动积分"),
        sa.Column("points_before", sa.Integer(), nullable=False, comment="变动前积分"),
        sa.Column("points_after", sa.Integer(), nullable=False, comment="变动后积分"),
        sa.Column("reason", sa.String(64), nullable=False, comment="变动原因"),
        sa.Column("reason_detail", sa.String(255), nullable=True, comment="详细说明"),
        sa.Column("ref_type", sa.String(32), nullable=True, comment="关联业务类型"),
        sa.Column("ref_id", sa.Integer(), nullable=True, comment="关联业务ID"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_point_record_user_id", "point_record", ["user_id"])
    op.create_index("ix_point_record_user_created", "point_record", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("point_record")
    op.drop_table("user_levels")
    op.drop_table("trust_score_record")
