from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    organizer_id: Mapped[int] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String(80), index=True)
    description: Mapped[str] = mapped_column(Text())
    category_id: Mapped[str] = mapped_column(String(32), index=True)
    city_code: Mapped[str] = mapped_column(String(16), index=True)
    location_name: Mapped[str] = mapped_column(String(128))
    address_detail: Mapped[str | None] = mapped_column(String(256), nullable=True)
    lat: Mapped[float] = mapped_column(Numeric(10, 7))
    lng: Mapped[float] = mapped_column(Numeric(10, 7))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_members: Mapped[int] = mapped_column(Integer())
    fee_type: Mapped[str] = mapped_column(String(16), default="free")
    fee_amount_cents: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    activity_status: Mapped[str] = mapped_column(String(24), default="published", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

