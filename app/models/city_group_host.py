from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CityGroupHost(Base):
    __tablename__ = "city_group_hosts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    city_code: Mapped[str] = mapped_column(String(32), index=True)
    user_id: Mapped[int] = mapped_column(index=True)
    role: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="active")
    appointed_by: Mapped[int | None] = mapped_column(nullable=True)
    appointed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    welcome_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    announcement: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    announcement_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_active_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CityGroupHostApplication(Base):
    __tablename__ = "city_group_host_applications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    city_code: Mapped[str] = mapped_column(String(32), index=True)
    user_id: Mapped[int] = mapped_column(index=True)
    application_type: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    intro_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    nominator_user_id: Mapped[int | None] = mapped_column(nullable=True)
    reviewer_admin_id: Mapped[int | None] = mapped_column(nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CityGroupHostAction(Base):
    __tablename__ = "city_group_host_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    host_id: Mapped[int] = mapped_column(index=True)
    city_code: Mapped[str] = mapped_column(String(32), index=True)
    actor_user_id: Mapped[int] = mapped_column()
    action: Mapped[str] = mapped_column(String(32))
    target_message_id: Mapped[int | None] = mapped_column(nullable=True)
    target_user_id: Mapped[int | None] = mapped_column(nullable=True)
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class CityGroupMute(Base):
    __tablename__ = "city_group_mutes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    city_code: Mapped[str] = mapped_column(String(32))
    user_id: Mapped[int] = mapped_column()
    muted_by_host_id: Mapped[int] = mapped_column()
    muted_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
