from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_serializer

from app.schemas.datetime_iso import (
    datetime_to_rfc3339_utc_z,
    datetime_to_rfc3339_utc_z_shanghai_naive,
)


class VerificationSummary(BaseModel):
    status: str
    canCreateActivity: bool


UserGender = Literal["male", "female", "unspecified"]


class MeData(BaseModel):
    userId: str
    phoneMasked: str
    nickname: str
    avatarUrl: str | None = None
    gender: UserGender | None = None
    bio: str = ""
    tags: list[str]
    status: str
    verification: VerificationSummary


class UpdateMeRequest(BaseModel):
    nickname: str | None = None
    avatarUrl: str | None = None
    bio: str | None = None
    tags: list[str] | None = None
    gender: UserGender | None = None


class MyActivitiesItem(BaseModel):
    activityId: str
    title: str
    startAt: datetime
    locationName: str
    categoryId: str
    activityStatus: str

    @field_serializer("startAt")
    def _ser_start_at(self, v: datetime) -> str:
        return datetime_to_rfc3339_utc_z(v) or ""


class MyActivitiesData(BaseModel):
    list: list[MyActivitiesItem]
    total: int
    page: int
    pageSize: int


class PremiumData(BaseModel):
    enabled: bool
    sku: list[str]


class MyChatItem(BaseModel):
    activityId: str
    title: str
    activityStatus: str
    memberCount: int
    lastMessage: str | None = None
    lastMessageAt: datetime | None = None
    unreadCount: int

    @field_serializer("lastMessageAt")
    def _ser_last_message_at(self, v: datetime | None) -> str | None:
        return datetime_to_rfc3339_utc_z_shanghai_naive(v)


class MyChatsData(BaseModel):
    list: list[MyChatItem]
    total: int
    page: int
    pageSize: int


class MyStatsData(BaseModel):
    joinedCount: int
    organizedCount: int
