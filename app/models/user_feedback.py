from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserFeedback(Base):
    """用户意见与建议（运营后台可读；用于早期收集反馈与回访）。"""

    __tablename__ = "user_feedbacks"

    id: Mapped[int] = mapped_column(BigInteger(), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger(), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    scene: Mapped[str] = mapped_column(String(32), index=True)
    description: Mapped[str] = mapped_column(Text())
    expectation: Mapped[str] = mapped_column(Text(), default="", server_default="")
    contact_willing: Mapped[bool] = mapped_column(Boolean(), default=False, server_default="0")
    contact_note: Mapped[str] = mapped_column(String(160), default="", server_default="")
    platform: Mapped[str] = mapped_column(String(16), default="mp-weixin", server_default="mp-weixin")
    app_version: Mapped[str] = mapped_column(String(32), default="", server_default="")
    status: Mapped[str] = mapped_column(String(16), default="new", server_default="new", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
