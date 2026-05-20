from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PayOrder(Base):
    __tablename__ = "wm_pay_orders"

    id: Mapped[int] = mapped_column(BigInteger(), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger(), index=True)
    qr_id: Mapped[str] = mapped_column(String(64))
    product: Mapped[str] = mapped_column(String(32), default="publish")
    out_trade_no: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    channel: Mapped[str] = mapped_column(String(16), default="native")
    #: 支付通道：wechat（官方 APIv3）| yungou（遗留，后期可下线）
    pay_provider: Mapped[str] = mapped_column(String(16), default="wechat")
    pay_code_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    platform_order_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    charge_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    money: Mapped[str] = mapped_column(String(16), default="1.00")
    attach: Mapped[str | None] = mapped_column(String(256), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
