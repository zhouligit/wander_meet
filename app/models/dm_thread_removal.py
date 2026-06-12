from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DmThreadRemoval(Base):
    """用户单方面删除好友：隐藏私聊会话，可再次申请恢复。"""

    __tablename__ = "dm_thread_removals"
    __table_args__ = (
        UniqueConstraint("user_id", "thread_id", name="uniq_dm_thread_removal"),
    )

    id: Mapped[int] = mapped_column(BigInteger(), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger(), index=True)
    thread_id: Mapped[int] = mapped_column(
        BigInteger(), ForeignKey("dm_threads.id", ondelete="CASCADE"), index=True
    )
    removed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
