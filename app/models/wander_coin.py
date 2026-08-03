"""晃晃币(WanderCoin)经济系统模型"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WanderCoinWallet(Base):
    """用户晃晃币钱包表"""

    __tablename__ = "wander_coin_wallets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
        comment="用户ID",
    )
    balance: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="当前余额"
    )
    total_earned: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="累计获得"
    )
    total_spent: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="累计消费"
    )
    frozen_amount: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="冻结金额（如置顶中）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
    )

    __table_args__ = (
        Index("idx_user_id", "user_id"),
    )


class WanderCoinTransaction(Base):
    """晃晃币交易流水表"""

    __tablename__ = "wander_coin_transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="用户ID",
    )
    amount: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="变动金额（正数=收入，负数=支出）",
    )
    balance_after: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="交易后余额"
    )
    tx_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="交易类型"
    )
    ref_type: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="关联业务类型"
    )
    ref_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="关联业务ID"
    )
    remark: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="备注"
    )
    expire_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="本笔过期时间（获得时设置）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now
    )

    __table_args__ = (
        Index("idx_user_time", "user_id", "created_at"),
        Index("idx_tx_type", "tx_type", "created_at"),
        Index("idx_expire", "expire_at"),
    )
