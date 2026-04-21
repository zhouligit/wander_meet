from pydantic import BaseModel, Field


class SendSMSCodeRequest(BaseModel):
    phone: str = Field(min_length=11, max_length=20)
    scene: str = "login"


class SendSMSCodeData(BaseModel):
    expireInSeconds: int = 1800


class SMSLoginRequest(BaseModel):
    phone: str = Field(min_length=11, max_length=20)
    code: str = Field(min_length=4, max_length=8)


class LoginUser(BaseModel):
    userId: str
    nickname: str
    avatarUrl: str | None = None
    status: str


class SMSLoginData(BaseModel):
    accessToken: str
    expiresIn: int
    refreshToken: str
    user: LoginUser


class RefreshTokenRequest(BaseModel):
    refreshToken: str


class RefreshTokenData(BaseModel):
    accessToken: str
    expiresIn: int

