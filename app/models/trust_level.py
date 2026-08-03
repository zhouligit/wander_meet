from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TrustScoreRecord(Base):
    """信誉分变动记录"""

    __tablename__ = "trust_score_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    change: Mapped[int] = mapped_column(Integer, comment="变动值（正数增加，负数减少）")
    trust_score_before: Mapped[int] = mapped_column(Integer, comment="变动前分数")
    trust_score_after: Mapped[int] = mapped_column(Integer, comment="变动后分数")
    reason: Mapped[str] = mapped_column(String(64), comment="变动原因")
    reason_detail: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="详细说明")
    ref_type: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="关联业务类型")
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="关联业务ID")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UserLevel(Base):
    """用户等级"""

    __tablename__ = "user_levels"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    total_points: Mapped[int] = mapped_column(Integer, default=0, comment="总积分")
    level_code: Mapped[str] = mapped_column(String(32), default="recruit", comment="等级代码")
    level_name: Mapped[str] = mapped_column(String(64), default="新兵", comment="等级名称")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PointRecord(Base):
    """积分变动记录"""

    __tablename__ = "point_record"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    points: Mapped[int] = mapped_column(Integer, comment="变动积分（正数增加，负数减少）")
    points_before: Mapped[int] = mapped_column(Integer, comment="变动前积分")
    points_after: Mapped[int] = mapped_column(Integer, comment="变动后积分")
    reason: Mapped[str] = mapped_column(String(64), comment="变动原因")
    reason_detail: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="详细说明")
    ref_type: Mapped[str | None] = mapped_column(String(32), nullable=True, comment="关联业务类型")
    ref_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="关联业务ID")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
