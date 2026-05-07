from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DmRequest(Base):
    __tablename__ = "dm_requests"

    id: Mapped[int] = mapped_column(BigInteger(), primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(BigInteger(), index=True)
    from_user_id: Mapped[int] = mapped_column(BigInteger(), index=True)
    to_user_id: Mapped[int] = mapped_column(BigInteger(), index=True)
    intro_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    thread_id: Mapped[int | None] = mapped_column(
        BigInteger(), ForeignKey("dm_threads.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
