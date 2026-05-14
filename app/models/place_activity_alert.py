from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlaceActivityAlert(Base):
    """用户订阅：某城市（及匹配规则）出现可报名活动时通知（推送由后续任务消费）。"""

    __tablename__ = "place_activity_alerts"

    id: Mapped[int] = mapped_column(BigInteger(), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger(), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    city_code: Mapped[str] = mapped_column(String(16), index=True)
    place_label: Mapped[str] = mapped_column(String(128))
    category_id: Mapped[str] = mapped_column(String(32), default="", server_default="")
    date_range: Mapped[str] = mapped_column(String(16), default="all", server_default="all")
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
