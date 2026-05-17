from pydantic import BaseModel, Field

from app.schemas.auth import LoginUser


class BindPhoneWechatRequest(BaseModel):
    phoneCode: str = Field(min_length=1, max_length=128)


class BindPhoneSmsRequest(BaseModel):
    phone: str = Field(min_length=11, max_length=20)
    code: str = Field(min_length=4, max_length=8)


class BindPhoneData(BaseModel):
    phoneMasked: str
    phoneBound: bool = True
    merged: bool = False
    #: 合并账号时下发新 token，前端应覆盖本地凭证
    accessToken: str | None = None
    expiresIn: int | None = None
    refreshToken: str | None = None
    user: LoginUser | None = None
