from datetime import datetime

from sqlalchemy import DateTime, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ActivityMediaAudit(Base):
    __tablename__ = "activity_media_audits"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(index=True)
    user_id: Mapped[int] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    image_urls: Mapped[list] = mapped_column(JSON)
    trace_entries: Mapped[list | None] = mapped_column(JSON, nullable=True)
    reject_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
