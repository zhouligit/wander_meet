from datetime import datetime

from pydantic import BaseModel, Field, field_serializer

from app.schemas.datetime_iso import datetime_to_rfc3339_utc_z_shanghai_naive


class AdminPhotoVerificationItem(BaseModel):
    verificationId: str
    userId: str
    nickname: str
    avatarUrl: str | None = None
    selfieUrl: str
    status: str
    submittedAt: datetime

    @field_serializer("submittedAt")
    def _ser_dt(self, v: datetime) -> str:
        return datetime_to_rfc3339_utc_z_shanghai_naive(v) or ""


class AdminPhotoVerificationListData(BaseModel):
    list: list[AdminPhotoVerificationItem]
    total: int
    page: int
    pageSize: int


class AdminPhotoVerificationRejectRequest(BaseModel):
    reason: str = Field(default="请重新拍摄", max_length=256)


class AdminPhotoVerificationActionData(BaseModel):
    verificationId: str
    userId: str
    status: str
