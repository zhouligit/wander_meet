from datetime import datetime

from sqlalchemy import BigInteger, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DmThread(Base):
    __tablename__ = "dm_threads"

    id: Mapped[int] = mapped_column(BigInteger(), primary_key=True, autoincrement=True)
    user_low_id: Mapped[int] = mapped_column(BigInteger(), index=True)
    user_high_id: Mapped[int] = mapped_column(BigInteger(), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
