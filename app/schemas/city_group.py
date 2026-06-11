from pydantic import BaseModel, Field


class CityHallJoinRequest(BaseModel):
    cityCode: str = Field(min_length=1, max_length=32)
    #: 可选展示名（标题与省内排序）；不传则用 cityCode
    cityLabel: str | None = Field(default=None, max_length=48)


class CityGroupHostSummary(BaseModel):
    userId: str
    nickname: str
    avatarUrl: str | None = None
    role: str
    badgeLabel: str


class CityHallLookupData(BaseModel):
    exists: bool
    cityCode: str
    displayName: str = ""
    memberCount: int = 0
    messageCount: int = 0
    unreadCount: int | None = None
    joined: bool | None = None
    activityId: str | None = None
    activityKind: str = "event"
    owner: CityGroupHostSummary | None = None
    announcement: str | None = None
    welcomeText: str | None = None
    currentUserHostRole: str | None = None
    canApplyForOwner: bool = False
    denyReason: str | None = None
    hostApplicationStatus: str | None = None
    ownerVacantDays: int = 0
    applyMinMembers: int = 100


class CityHallJoinData(BaseModel):
    cityCode: str
    displayName: str
    memberCount: int
    joined: bool
    activityId: str
    enrollmentId: str


class CityGroupsMetaData(BaseModel):
    recommendTip: str
    userCanCreate: bool


class CityHallCatalogCity(BaseModel):
    cityCode: str
    cityName: str
    displayName: str
    memberCount: int
    #: 尚无用户触发创建时为 ``None``
    activityId: str | None = None
    joined: bool | None = None
    ownerNickname: str | None = None


class CityHallCatalogProvince(BaseModel):
    provinceCode: str
    provinceName: str
    cities: list[CityHallCatalogCity]


class CityHallCatalogData(BaseModel):
    provinces: list[CityHallCatalogProvince]


class CityGroupProfileData(BaseModel):
    cityCode: str
    displayName: str = ""
    memberCount: int = 0
    activityId: str | None = None
    owner: CityGroupHostSummary | None = None
    deputies: list[CityGroupHostSummary] = Field(default_factory=list)
    announcement: str | None = None
    welcomeText: str | None = None
    currentUserHostRole: str | None = None
    canApplyForOwner: bool = False
    denyReason: str | None = None
    hostApplicationStatus: str | None = None
    ownerVacantDays: int = 0
    applyMinMembers: int = 100


class CityGroupHostContextData(BaseModel):
    cityCode: str
    activityId: str
    owner: CityGroupHostSummary | None = None
    deputies: list[CityGroupHostSummary] = Field(default_factory=list)
    currentUserHostRole: str | None = None
    canModerate: bool = False
    hostUserIds: list[str] = Field(default_factory=list)


class CityGroupHostProfilePatchRequest(BaseModel):
    cityCode: str = Field(min_length=1, max_length=32)
    welcomeText: str | None = Field(default=None, max_length=500)
    announcement: str | None = Field(default=None, max_length=1000)
    clearWelcome: bool = False
    clearAnnouncement: bool = False


class CityGroupHostMuteRequest(BaseModel):
    cityCode: str = Field(min_length=1, max_length=32)
    userId: str = Field(min_length=1, max_length=32)


class CityGroupHostMuteData(BaseModel):
    mutedUntil: str


class CityGroupHostDeleteMessageRequest(BaseModel):
    cityCode: str = Field(min_length=1, max_length=32)


class CityHostBadgeItem(BaseModel):
    cityCode: str
    cityName: str
    role: str
    badgeLabel: str


class AdminCityGroupHostItem(BaseModel):
    id: int
    cityCode: str
    userId: str
    nickname: str
    role: str
    status: str
    appointedAt: str


class AdminCityGroupHostListData(BaseModel):
    list: list[AdminCityGroupHostItem]
    total: int
    page: int
    pageSize: int


class AdminAppointCityGroupHostRequest(BaseModel):
    cityCode: str = Field(min_length=1, max_length=32)
    userId: str = Field(min_length=1, max_length=32)
    role: str = Field(pattern="^(owner|deputy)$")


class AdminAppointCityGroupHostData(BaseModel):
    id: int
    cityCode: str
    userId: str
    role: str
    status: str


class AdminUpdateCityGroupHostRequest(BaseModel):
    status: str = Field(pattern="^(active|suspended|resigned)$")


class CityGroupHostEligibilityData(BaseModel):
    canApplyForOwner: bool = False
    denyReason: str | None = None
    hostApplicationStatus: str | None = None
    ownerVacantDays: int = 0
    applyMinMembers: int = 100


class CityGroupHostApplicationRequest(BaseModel):
    cityCode: str = Field(min_length=1, max_length=32)
    introText: str | None = Field(default=None, max_length=500)


class CityGroupHostApplicationData(BaseModel):
    applicationId: int
    cityCode: str
    status: str
    applicationType: str


class CityGroupNominateDeputyRequest(BaseModel):
    cityCode: str = Field(min_length=1, max_length=32)
    userId: str = Field(min_length=1, max_length=32)


class CityGroupRecommendActivityRequest(BaseModel):
    cityCode: str = Field(min_length=1, max_length=32)
    activityId: str = Field(min_length=1, max_length=32)


class AdminCityGroupHostApplicationItem(BaseModel):
    applicationId: int
    cityCode: str
    userId: str
    nickname: str
    applicationType: str
    status: str
    introText: str | None = None
    nominatorUserId: str | None = None
    createdAt: str


class AdminCityGroupHostApplicationListData(BaseModel):
    list: list[AdminCityGroupHostApplicationItem]
    total: int
    page: int
    pageSize: int


class AdminRejectHostApplicationRequest(BaseModel):
    reviewNote: str | None = Field(default=None, max_length=256)


class AdminSweepInactiveHostsData(BaseModel):
    resignedCount: int
