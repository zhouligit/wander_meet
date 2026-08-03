"""信誉分和积分申诉模型"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TrustScoreAppeal(Base):
    """信誉分申诉表"""

    __tablename__ = "trust_score_appeals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="申诉用户ID",
    )
    record_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("trust_score_records.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联的信誉分变动记录ID",
    )
    appeal_reason: Mapped[str] = mapped_column(
        Text, nullable=False, comment="申诉理由"
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        comment="申诉状态: pending/rejected/approved",
    )
    reviewer_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="审核人ID",
    )
    review_comment: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="审核意见"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="审核时间"
    )

    __table_args__ = (
        Index("idx_user_status", "user_id", "status"),
        Index("idx_record_id", "record_id"),
    )


class PointAppeal(Base):
    """积分申诉表"""

    __tablename__ = "point_appeals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="申诉用户ID",
    )
    record_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("point_records.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联的积分变动记录ID",
    )
    appeal_reason: Mapped[str] = mapped_column(
        Text, nullable=False, comment="申诉理由"
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        comment="申诉状态: pending/rejected/approved",
    )
    reviewer_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="审核人ID",
    )
    review_comment: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="审核意见"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="审核时间"
    )

    __table_args__ = (
        Index("idx_user_status", "user_id", "status"),
        Index("idx_record_id", "record_id"),
    )
