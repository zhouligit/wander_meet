from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    #: ``event`` 普通活动；``city_hall`` 城市大群（虚拟活动，复用报名与群聊表）
    activity_kind: Mapped[str] = mapped_column(String(20), default="event", server_default="event")
    #: 城市大群：省级代码 ``XX0000``，用于目录分组与排序
    city_hall_province_code: Mapped[str | None] = mapped_column(String(8), nullable=True, index=True)
    #: 城市大群：省内排序键（展示名小写或城市码小写，兼容首字母/区划序）
    city_hall_sort_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: 城市大群：城市码（与 ``/city-groups`` 的 cityCode 一致；库表由迁移 ``uq_activities_city_hall_city_code`` 唯一约束）
    city_hall_city_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    organizer_id: Mapped[int] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String(80), index=True)
    description: Mapped[str] = mapped_column(Text())
    category_id: Mapped[str] = mapped_column(String(32), index=True)
    #: ``category_id=other`` 时的自定义主题（2～16 字）
    category_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    #: 二级分类，如 ``sports`` + ``basketball``
    sub_category_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    city_code: Mapped[str] = mapped_column(String(16), index=True)
    location_name: Mapped[str] = mapped_column(String(128))
    address_detail: Mapped[str | None] = mapped_column(String(256), nullable=True)
    lat: Mapped[float] = mapped_column(Numeric(10, 7))
    lng: Mapped[float] = mapped_column(Numeric(10, 7))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: 实际结束/取消时刻（冗余，便于 ``timeScope=past`` 索引与排序；计划结束见 ``end_at``）
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_members: Mapped[int] = mapped_column(Integer())
    fee_type: Mapped[str] = mapped_column(String(16), default="free")
    fee_amount_cents: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    activity_status: Mapped[str] = mapped_column(String(24), default="published", index=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    images: Mapped[list | None] = mapped_column(JSON, nullable=True)
    #: none | pending | pass | reject
    images_audit_status: Mapped[str] = mapped_column(String(16), default="none", index=True)
    images_audit_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

