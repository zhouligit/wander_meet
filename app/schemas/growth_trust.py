from datetime import datetime

from pydantic import BaseModel, Field, field_serializer

from app.schemas.datetime_iso import datetime_to_rfc3339_utc_z_shanghai_naive


class ReferralBindRequest(BaseModel):
    code: str


class ReferralRecordItem(BaseModel):
    inviteeNickname: str
    status: str
    qualifiedAction: str | None = None
    createdAt: datetime
    qualifiedAt: datetime | None = None

    @field_serializer("createdAt", "qualifiedAt")
    def _ser_dt(self, v: datetime | None) -> str | None:
        return datetime_to_rfc3339_utc_z_shanghai_naive(v)


class ReferralData(BaseModel):
    code: str
    sharePath: str
    qualifiedCount: int
    pendingCount: int
    photoVerified: bool
    nextTier: int | None = None
    nextTierProgress: float
    tiers: list[int]
    records: list[ReferralRecordItem]


class ReferralBindingData(BaseModel):
    status: str
    inviterId: str | None = None


class EntitlementItem(BaseModel):
    id: str
    entitlementType: str
    startsAt: datetime
    expiresAt: datetime
    pinQuotaRemaining: int
    source: str

    @field_serializer("startsAt", "expiresAt")
    def _ser_dt(self, v: datetime) -> str:
        return datetime_to_rfc3339_utc_z_shanghai_naive(v) or ""


class EntitlementsData(BaseModel):
    list: list[EntitlementItem]


class PremiumEntitlement(BaseModel):
    active: bool = False
    tier: str | None = None
    expiresAt: datetime | None = None
    pinQuotaRemaining: int = 0
    badges: list[str] = Field(default_factory=list)

    @field_serializer("expiresAt")
    def _ser_exp(self, v: datetime | None) -> str | None:
        return datetime_to_rfc3339_utc_z_shanghai_naive(v)


class PremiumDataExtended(BaseModel):
    enabled: bool
    sku: list[str] = Field(default_factory=list)
    entitlement: PremiumEntitlement = Field(default_factory=PremiumEntitlement)


class PinActivityData(BaseModel):
    activityId: str
    pinnedUntil: datetime

    @field_serializer("pinnedUntil")
    def _ser_pin(self, v: datetime) -> str:
        return datetime_to_rfc3339_utc_z_shanghai_naive(v) or ""


class PendingCheckinItem(BaseModel):
    activityId: str
    title: str
    startAt: datetime
    locationName: str
    checkinOpen: bool
    checkedIn: bool
    windowEnd: datetime | None = None

    @field_serializer("startAt", "windowEnd")
    def _ser_dt(self, v: datetime | None) -> str | None:
        return datetime_to_rfc3339_utc_z_shanghai_naive(v)


class PendingCheckinsData(BaseModel):
    list: list[PendingCheckinItem]


class CheckinRequest(BaseModel):
    photoUrl: str | None = None


class CheckinData(BaseModel):
    activityId: str
    checkedInAt: datetime

    @field_serializer("checkedInAt")
    def _ser_dt(self, v: datetime) -> str:
        return datetime_to_rfc3339_utc_z_shanghai_naive(v) or ""


class MeetReviewCandidate(BaseModel):
    userId: str
    nickname: str
    avatarUrl: str | None = None


class MeetReviewCandidatesData(BaseModel):
    list: list[MeetReviewCandidate]


class MeetReviewSubmitRequest(BaseModel):
    toUserId: str
    met: bool
    tags: list[str] = Field(default_factory=list)
    comment: str | None = None


class MeetHistoryItem(BaseModel):
    activityId: str
    title: str
    startAt: datetime | None = None
    success: bool
    checkedIn: bool

    @field_serializer("startAt")
    def _ser_dt(self, v: datetime | None) -> str | None:
        return datetime_to_rfc3339_utc_z_shanghai_naive(v)


class MeetHistoryData(BaseModel):
    list: list[MeetHistoryItem]


class PhotoVerificationStatusData(BaseModel):
    status: str | None = None
    rejectReason: str | None = None
    submittedAt: datetime | None = None
    reviewedAt: datetime | None = None

    @field_serializer("submittedAt", "reviewedAt")
    def _ser_dt(self, v: datetime | None) -> str | None:
        return datetime_to_rfc3339_utc_z_shanghai_naive(v)


class PhotoVerificationSubmitRequest(BaseModel):
    selfieUrl: str


class SafetyAckRequest(BaseModel):
    ackType: str = "enroll_first"


class SafetyAckData(BaseModel):
    ackType: str
    ackAt: datetime

    @field_serializer("ackAt")
    def _ser_dt(self, v: datetime) -> str:
        return datetime_to_rfc3339_utc_z_shanghai_naive(v) or ""


class SafetyGuideSection(BaseModel):
    title: str
    body: str


class SafetyGuideData(BaseModel):
    format: str = "sections"
    sections: list[SafetyGuideSection] = Field(default_factory=list)


class PhotoVerificationUploadData(BaseModel):
    selfieUrl: str


class ShowMeetCountData(BaseModel):
    showMeetCount: bool


class BadgeVisibilityData(BaseModel):
    badgeId: str
    visible: bool


class OrganizerExposureData(BaseModel):
    qualifiedReferrals: int
    nextTier: int | None = None
    nextTierProgress: float
    tiers: list[int]


class BadgeVisibilityRequest(BaseModel):
    badgeId: str
    visible: bool


class ShowMeetCountRequest(BaseModel):
    showMeetCount: bool


class TrustBadgeItem(BaseModel):
    badgeId: str
    grantedAt: datetime
    visible: bool

    @field_serializer("grantedAt")
    def _ser_dt(self, v: datetime) -> str:
        return datetime_to_rfc3339_utc_z_shanghai_naive(v) or ""


class PhotoVerificationSummary(BaseModel):
    status: str | None = None
    rejectReason: str | None = None
    submittedAt: datetime | None = None

    @field_serializer("submittedAt")
    def _ser_dt(self, v: datetime | None) -> str | None:
        return datetime_to_rfc3339_utc_z_shanghai_naive(v)


class RealnameVerificationSummary(BaseModel):
    status: str | None = None
    label: str = "实名认证（可选）"


class TrustData(BaseModel):
    trustLevel: str
    trustScoreSummary: str
    meetCount: int
    showMeetCount: bool
    photoVerified: bool
    photoVerification: PhotoVerificationSummary
    realnameVerification: RealnameVerificationSummary
    profileComplete: bool
    qualifiedReferrals: int
    badges: list[TrustBadgeItem]
