from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_serializer

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
    countryCode: str | None = None
    travelerRoles: list[str] = Field(default_factory=list)
    currentPlace: str | None = None
    stayKind: str | None = None
    stayEndAt: str | None = None
    acquisitionSource: str | None = None
    notifyPrefs: dict | None = None
    showDistance: bool = True
    onboardingCompletedAt: str | None = None


class UpdateMeRequest(BaseModel):
    nickname: str | None = None
    avatarUrl: str | None = None
    bio: str | None = None
    tags: list[str] | None = None
    gender: UserGender | None = None
    countryCode: str | None = None
    travelerRoles: list[str] | None = None
    currentPlace: str | None = None
    stayKind: str | None = None
    stayEndAt: str | None = None
    acquisitionSource: str | None = None
    notifyPrefs: dict | None = None
    showDistance: bool | None = None
    completeOnboarding: bool | None = None


class MyActivitiesItem(BaseModel):
    activityId: str
    #: ``event`` 普通活动；``city_hall`` 城市大群（默认兼容旧客户端）
    activityKind: str = "event"
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
    #: ``event`` | ``city_hall``，默认 ``event`` 兼容旧客户端
    activityKind: str = "event"
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
