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
    #: 是否已绑定大陆手机号（微信一键登录用户初始为 false）
    phoneBound: bool = False
    emailMasked: str = ""
    #: 是否已注册邮箱密码账号（H5）
    emailBound: bool = False
    nickname: str
    avatarUrl: str | None = None
    gender: UserGender | None = None
    birthDate: str | None = None
    profileComplete: bool = False
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
    #: 运营管理员（``users.role=admin``），可进小程序审核入口
    isAdmin: bool = False


class UpdateMeRequest(BaseModel):
    nickname: str | None = None
    avatarUrl: str | None = None
    bio: str | None = None
    tags: list[str] | None = None
    gender: UserGender | None = None
    birthDate: str | None = None
    countryCode: str | None = None
    travelerRoles: list[str] | None = None
    currentPlace: str | None = None
    stayKind: str | None = None
    stayEndAt: str | None = None
    acquisitionSource: str | None = None
    notifyPrefs: dict | None = None
    showDistance: bool | None = None
    completeOnboarding: bool | None = None


class AvatarUploadUrlRequest(BaseModel):
    contentType: str | None = None
    fileExt: str


class AvatarUploadUrlData(BaseModel):
    uploadUrl: str
    objectKey: str
    publicUrl: str
    headers: dict[str, str] = Field(default_factory=dict)


class ChatImageUploadData(BaseModel):
    imageUrl: str


class MyActivitiesItem(BaseModel):
    activityId: str
    #: ``event`` 普通活动；``city_hall`` 城市大群（默认兼容旧客户端）
    activityKind: str = "event"
    title: str
    startAt: datetime
    locationName: str
    categoryId: str
    categoryLabel: str = ""
    endAt: datetime | None = None
    activityStatus: str

    @field_serializer("startAt")
    def _ser_start_at(self, v: datetime) -> str:
        return datetime_to_rfc3339_utc_z(v) or ""

    @field_serializer("endAt")
    def _ser_end_at(self, v: datetime | None) -> str | None:
        return datetime_to_rfc3339_utc_z(v) if v else None


class MyActivitiesData(BaseModel):
    list: list[MyActivitiesItem]
    total: int
    page: int
    pageSize: int
    #: ``role=joined`` 时返回，与 ``total`` 一致：cityHallCount + eventCount == total
    cityHallCount: int | None = None
    eventCount: int | None = None


class PremiumEntitlementSummary(BaseModel):
    active: bool = False
    tier: str | None = None
    expiresAt: datetime | None = None
    pinQuotaRemaining: int = 0
    badges: list[str] = Field(default_factory=list)

    @field_serializer("expiresAt")
    def _ser_exp(self, v: datetime | None) -> str | None:
        return datetime_to_rfc3339_utc_z_shanghai_naive(v)


class PremiumData(BaseModel):
    enabled: bool
    sku: list[str] = Field(default_factory=list)
    entitlement: PremiumEntitlementSummary = Field(default_factory=PremiumEntitlementSummary)


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


class MessageUnreadSummaryData(BaseModel):
    chatUnread: int = 0
    notifUnread: int = 0
