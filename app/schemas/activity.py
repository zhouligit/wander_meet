from datetime import datetime

from pydantic import BaseModel, Field, field_serializer

from app.schemas.datetime_iso import (
    datetime_to_rfc3339_utc_z,
    datetime_to_rfc3339_utc_z_shanghai_naive,
)


class ActivityCard(BaseModel):
    activityId: str
    title: str
    startAt: datetime
    locationName: str
    lat: float
    lng: float
    distanceMeters: int | None = None
    enrolledCount: int
    maxMembers: int
    categoryId: str
    subCategoryId: str = ""
    categoryLabel: str = ""
    categoryDisplay: str = ""
    activityStatus: str
    enrollmentStatus: str | None = None

    @field_serializer("startAt")
    def _ser_start_at(self, v: datetime) -> str:
        return datetime_to_rfc3339_utc_z(v) or ""


class ActivityListData(BaseModel):
    list: list[ActivityCard]
    total: int
    page: int
    pageSize: int


class NearbySearchCenter(BaseModel):
    lat: float
    lng: float


class NearbyActivityListData(BaseModel):
    list: list[ActivityCard]
    total: int
    page: int
    pageSize: int
    searchCenter: NearbySearchCenter
    radiusKm: float


class CreateActivityRequest(BaseModel):
    title: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=1)
    categoryId: str
    categoryLabel: str | None = Field(default=None, max_length=32)
    subCategoryId: str | None = Field(default=None, max_length=32)
    startAt: datetime
    endAt: datetime | None = None
    cityCode: str
    locationName: str
    addressDetail: str | None = None
    lat: float
    lng: float
    maxMembers: int = Field(ge=2, le=100)
    feeType: str = "free"
    feeAmount: int | None = None


class ActivityDetailOrganizer(BaseModel):
    userId: str
    nickname: str
    avatarUrl: str | None = None
    bio: str = ""
    tags: list[str] = Field(default_factory=list)


class MyEnrollment(BaseModel):
    status: str


class ActivityDetailData(BaseModel):
    activityId: str
    #: ``event`` 普通活动；``city_hall`` 城市大群（前向兼容：缺省视为 event）
    activityKind: str = "event"
    title: str
    description: str
    categoryId: str
    subCategoryId: str = ""
    categoryLabel: str = ""
    categoryDisplay: str = ""
    startAt: datetime
    endAt: datetime | None = None
    cityCode: str
    locationName: str
    addressDetail: str | None = None
    lat: float
    lng: float
    maxMembers: int
    feeType: str
    feeAmount: int | None = None
    activityStatus: str
    organizer: ActivityDetailOrganizer
    enrolledCount: int
    myEnrollment: MyEnrollment | None = None

    @field_serializer("startAt", "endAt")
    def _ser_detail_times(self, v: datetime | None) -> str | None:
        return datetime_to_rfc3339_utc_z(v)


class EnrollmentData(BaseModel):
    enrollmentId: str
    status: str


class UpdateActivityRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=80)
    description: str | None = None
    categoryId: str | None = None
    categoryLabel: str | None = Field(default=None, max_length=32)
    subCategoryId: str | None = Field(default=None, max_length=32)
    startAt: datetime | None = None
    endAt: datetime | None = None
    locationName: str | None = None
    addressDetail: str | None = None
    lat: float | None = None
    lng: float | None = None
    maxMembers: int | None = Field(default=None, ge=2, le=100)
    feeType: str | None = None
    feeAmount: int | None = None


class ActivityMemberItem(BaseModel):
    userId: str
    nickname: str
    avatarUrl: str | None = None
    role: str
    joinedAt: datetime

    @field_serializer("joinedAt")
    def _ser_joined_at(self, v: datetime) -> str:
        return datetime_to_rfc3339_utc_z_shanghai_naive(v) or ""


class ActivityMembersData(BaseModel):
    list: list[ActivityMemberItem]


class ChatMessageSender(BaseModel):
    userId: str
    nickname: str
    avatarUrl: str | None = None


class ChatMessageItem(BaseModel):
    messageId: str
    activityId: str
    sender: ChatMessageSender
    msgType: str
    text: str | None = None
    imageUrl: str | None = None
    stickerId: str | None = None
    locationName: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    createdAt: datetime
    senderHostRole: str | None = None

    @field_serializer("createdAt")
    def _ser_created_at(self, v: datetime) -> str:
        return datetime_to_rfc3339_utc_z_shanghai_naive(v) or ""


class ChatMessagesData(BaseModel):
    list: list[ChatMessageItem]
    nextCursor: str | None = None


class SendMessageRequest(BaseModel):
    msgType: str
    text: str | None = None
    imageUrl: str | None = None
    stickerId: str | None = None
    locationName: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None

