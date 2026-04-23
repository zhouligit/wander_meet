from datetime import datetime

from pydantic import BaseModel


class VerificationSummary(BaseModel):
    status: str
    canCreateActivity: bool


class MeData(BaseModel):
    userId: str
    phoneMasked: str
    nickname: str
    avatarUrl: str | None = None
    tags: list[str]
    status: str
    verification: VerificationSummary


class UpdateMeRequest(BaseModel):
    nickname: str | None = None
    avatarUrl: str | None = None
    tags: list[str] | None = None


class MyActivitiesItem(BaseModel):
    activityId: str
    title: str
    startAt: datetime
    locationName: str
    categoryId: str
    activityStatus: str


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


class MyChatsData(BaseModel):
    list: list[MyChatItem]
    total: int
    page: int
    pageSize: int
