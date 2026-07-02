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
    messageCount: int = 0
    unreadCount: int | None = None
    coverImageUrl: str | None = None

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
    images: list[str] | None = Field(default=None, max_length=9)
    guideSections: dict[str, str] | None = None
    requireEnrollmentIdentity: bool = False


class ActivityGuideTemplateSection(BaseModel):
    key: str
    label: str
    ordinal: str
    placeholder: str = ""


class ActivityGuideTemplateData(BaseModel):
    sections: list[ActivityGuideTemplateSection]
    overviewPlaceholder: str = ""


class ActivityGuideSyncedOverview(BaseModel):
    title: str
    startAt: datetime
    endAt: datetime | None = None
    locationName: str
    addressDetail: str | None = None
    maxMembers: int
    enrolledCount: int
    feeType: str
    feeAmount: int | None = None
    feeLabel: str

    @field_serializer("startAt", "endAt")
    def _ser_guide_times(self, v: datetime | None) -> str | None:
        return datetime_to_rfc3339_utc_z(v)


class ActivityDetailOrganizer(BaseModel):
    userId: str
    nickname: str
    avatarUrl: str | None = None
    bio: str = ""
    tags: list[str] = Field(default_factory=list)


class MyEnrollmentIdentity(BaseModel):
    participantName: str = ""
    idCardMasked: str = ""
    phoneMasked: str = ""
    canEditIdentity: bool = False


class MyEnrollment(BaseModel):
    status: str
    identity: MyEnrollmentIdentity | None = None


class EnrollmentIdentityPrefillData(BaseModel):
    participantName: str = ""
    idCardNumber: str = ""
    phoneMasked: str = ""


class EnrollActivityRequest(BaseModel):
    participantName: str | None = Field(default=None, max_length=32)
    idCardNumber: str | None = Field(default=None, max_length=18)


class UpdateEnrollmentIdentityRequest(BaseModel):
    participantName: str = Field(min_length=2, max_length=32)
    idCardNumber: str = Field(min_length=18, max_length=18)


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
    requireEnrollmentIdentity: bool = False
    coverImageUrl: str | None = None
    images: list[str] | None = None
    imagesAuditStatus: str = "none"
    guideSections: dict[str, str] | None = None
    guideFilled: bool = False
    guideOverview: ActivityGuideSyncedOverview | None = None
    #: 当前登录用户是否为活动发起人（未登录恒为 false）
    isOrganizer: bool = False

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
    images: list[str] | None = Field(default=None, max_length=9)
    guideSections: dict[str, str] | None = None
    requireEnrollmentIdentity: bool | None = None


class CancelActivityRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=512)


class ActivityMemberIdentity(BaseModel):
    participantName: str = ""
    idCardMasked: str = ""
    phoneMasked: str = ""


class ActivityMemberItem(BaseModel):
    userId: str
    nickname: str
    avatarUrl: str | None = None
    role: str
    joinedAt: datetime
    identity: ActivityMemberIdentity | None = None

    @field_serializer("joinedAt")
    def _ser_joined_at(self, v: datetime) -> str:
        return datetime_to_rfc3339_utc_z_shanghai_naive(v) or ""


class ActivityMembersData(BaseModel):
    list: list[ActivityMemberItem]


class ChatMentionItem(BaseModel):
    userId: str
    nickname: str
    start: int | None = None
    end: int | None = None


class ChainSignupEntryItem(BaseModel):
    entryId: str
    userId: str
    nickname: str
    note: str = ""
    createdAt: datetime

    @field_serializer("createdAt")
    def _ser_created_at(self, v: datetime) -> str:
        return datetime_to_rfc3339_utc_z_shanghai_naive(v) or ""


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
    recActivityId: str | None = None
    recActivityTitle: str | None = None
    chainTitle: str | None = None
    chainDescription: str | None = None
    chainClosed: bool | None = None
    chainEntries: list[ChainSignupEntryItem] | None = None
    mentions: list[ChatMentionItem] | None = None

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
    chainTitle: str | None = Field(default=None, max_length=80)
    chainDescription: str | None = Field(default=None, max_length=200)
    chainNote: str | None = Field(default=None, max_length=60)
    mentions: list[ChatMentionItem] | None = None


class ChainSignupEntryRequest(BaseModel):
    note: str | None = Field(default=None, max_length=60)

