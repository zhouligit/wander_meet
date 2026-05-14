from datetime import datetime

from pydantic import BaseModel, Field, field_serializer

from app.schemas.datetime_iso import datetime_to_rfc3339_utc_z


class PlaceSuggestionItem(BaseModel):
    cityCode: str
    cityName: str
    provinceCode: str
    provinceName: str


class PlaceSuggestionsData(BaseModel):
    list: list[PlaceSuggestionItem]


class CreatePlaceActivityAlertRequest(BaseModel):
    cityCode: str = Field(min_length=1, max_length=16)
    placeLabel: str = Field(min_length=1, max_length=128)
    categoryId: str | None = Field(default=None, max_length=32)
    dateRange: str = Field(default="all", pattern="^(all|today|tomorrow)$")


class PlaceActivityAlertItem(BaseModel):
    alertId: str
    cityCode: str
    placeLabel: str
    categoryId: str
    dateRange: str
    status: str
    createdAt: datetime

    @field_serializer("createdAt")
    def _ser_created(self, v: datetime) -> str:
        return datetime_to_rfc3339_utc_z(v) or ""


class PlaceActivityAlertListData(BaseModel):
    list: list[PlaceActivityAlertItem]


class PlaceActivityAlertCreateData(BaseModel):
    alertId: str
    cityCode: str
    placeLabel: str
    categoryId: str
    dateRange: str
    createdAt: datetime

    @field_serializer("createdAt")
    def _ser_created(self, v: datetime) -> str:
        return datetime_to_rfc3339_utc_z(v) or ""
