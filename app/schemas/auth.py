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


class EmailRegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    nickname: str | None = Field(default=None, max_length=32)


class EmailLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class EmailForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class EmailForgotPasswordData(BaseModel):
    expireInSeconds: int


class EmailResetPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    code: str = Field(min_length=4, max_length=8)
    newPassword: str = Field(min_length=8, max_length=128)


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

