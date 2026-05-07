from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DirectMessage(Base):
    __tablename__ = "direct_messages"

    id: Mapped[int] = mapped_column(BigInteger(), primary_key=True, autoincrement=True)
    thread_id: Mapped[int] = mapped_column(
        BigInteger(), ForeignKey("dm_threads.id", ondelete="CASCADE"), index=True
    )
    sender_id: Mapped[int] = mapped_column(BigInteger(), index=True)
    msg_type: Mapped[str] = mapped_column(String(16), default="text")
    text_content: Mapped[str | None] = mapped_column(Text(), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
