from datetime import datetime

from sqlalchemy import Boolean, DateTime, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    phone_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    #: 本小程序 openid（微信一键登录）
    mp_openid: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    mp_unionid: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    nickname: Mapped[str] = mapped_column(String(32))
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    traveler_roles: Mapped[list | None] = mapped_column(JSON, nullable=True)
    current_place: Mapped[str | None] = mapped_column(String(256), nullable=True)
    stay_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    stay_end_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acquisition_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notify_prefs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    show_distance: Mapped[bool] = mapped_column(Boolean(), default=True)
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), default="active")
    role: Mapped[str] = mapped_column(String(16), default="user")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

