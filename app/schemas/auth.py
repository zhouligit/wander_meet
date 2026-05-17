from pydantic import BaseModel, Field


class SendSMSCodeRequest(BaseModel):
    phone: str = Field(min_length=11, max_length=20)
    scene: str = "login"


class SendSMSCodeData(BaseModel):
    expireInSeconds: int = 300


class SMSLoginRequest(BaseModel):
    phone: str = Field(min_length=11, max_length=20)
    code: str = Field(min_length=4, max_length=8)


class WechatLoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=128)


class LoginUser(BaseModel):
    userId: str
    nickname: str
    avatarUrl: str | None = None
    gender: str | None = None
    status: str
    onboardingCompletedAt: str | None = None


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
    refreshToken: str


class LogoutData(BaseModel):
    status: str = "ok"

