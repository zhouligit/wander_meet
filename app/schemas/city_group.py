from pydantic import BaseModel, Field


class CityHallJoinRequest(BaseModel):
    cityCode: str = Field(min_length=1, max_length=32)
    #: 可选展示名（标题与省内排序）；不传则用 cityCode
    cityLabel: str | None = Field(default=None, max_length=48)


class CityHallLookupData(BaseModel):
    exists: bool
    cityCode: str
    displayName: str = ""
    memberCount: int = 0
    joined: bool | None = None
    activityId: str | None = None
    activityKind: str = "event"


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


class CityHallCatalogProvince(BaseModel):
    provinceCode: str
    provinceName: str
    cities: list[CityHallCatalogCity]


class CityHallCatalogData(BaseModel):
    provinces: list[CityHallCatalogProvince]
