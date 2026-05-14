from pydantic import BaseModel, Field


class CityHallJoinRequest(BaseModel):
    cityCode: str = Field(min_length=1, max_length=32)


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
