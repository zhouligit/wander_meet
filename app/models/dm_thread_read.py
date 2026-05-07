from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DmThreadRead(Base):
    __tablename__ = "dm_thread_reads"
    __table_args__ = (UniqueConstraint("user_id", "thread_id", name="uniq_dm_thread_read"),)

    id: Mapped[int] = mapped_column(BigInteger(), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger(), index=True)
    thread_id: Mapped[int] = mapped_column(
        BigInteger(), ForeignKey("dm_threads.id", ondelete="CASCADE"), index=True
    )
    last_read_message_id: Mapped[int] = mapped_column(BigInteger(), default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
