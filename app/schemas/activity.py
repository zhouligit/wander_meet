from datetime import datetime

from pydantic import BaseModel, Field


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
    activityStatus: str
    enrollmentStatus: str | None = None


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


class MyEnrollment(BaseModel):
    status: str


class ActivityDetailData(BaseModel):
    activityId: str
    title: str
    description: str
    categoryId: str
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


class EnrollmentData(BaseModel):
    enrollmentId: str
    status: str


class UpdateActivityRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=80)
    description: str | None = None
    categoryId: str | None = None
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
    createdAt: datetime


class ChatMessagesData(BaseModel):
    list: list[ChatMessageItem]
    nextCursor: str | None = None


class SendMessageRequest(BaseModel):
    msgType: str
    text: str | None = None
    imageUrl: str | None = None

