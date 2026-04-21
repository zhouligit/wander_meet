import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, decode_access_token, hash_phone
from app.db.session import get_db_session, redis_client
from app.models.user import User
from app.schemas.auth import (
    LoginUser,
    RefreshTokenData,
    RefreshTokenRequest,
    SMSLoginData,
    SMSLoginRequest,
    SendSMSCodeData,
    SendSMSCodeRequest,
)
from app.schemas.common import APIResponse

router = APIRouter(prefix="/auth", tags=["auth"])
SMS_CODE_TTL_SECONDS = 1800


@router.post("/sms/send")
async def send_sms_code(payload: SendSMSCodeRequest) -> APIResponse[SendSMSCodeData]:
    code = f"{random.randint(100000, 999999)}"
    redis_key = f"wm:sms:{payload.scene}:{payload.phone}"
    await redis_client.set(redis_key, code, ex=SMS_CODE_TTL_SECONDS)
    # v0.1 demo env: write code to logs/redis only; integrate SMS provider later.
    return APIResponse(data=SendSMSCodeData(expireInSeconds=SMS_CODE_TTL_SECONDS))


@router.post("/sms/login")
async def sms_login(
    payload: SMSLoginRequest, db: AsyncSession = Depends(get_db_session)
) -> APIResponse[SMSLoginData]:
    redis_key = f"wm:sms:login:{payload.phone}"
    cached_code = await redis_client.get(redis_key)
    if not cached_code or cached_code != payload.code:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    phone_hash = hash_phone(payload.phone)
    user = await db.scalar(select(User).where(User.phone_hash == phone_hash))
    if not user:
        user = User(phone_hash=phone_hash, nickname=f"旅人{payload.phone[-4:]}")
        db.add(user)
        await db.commit()
        await db.refresh(user)

    access_token = create_access_token(user.id)
    response_data = SMSLoginData(
        accessToken=access_token,
        expiresIn=7200,
        refreshToken=access_token,
        user=LoginUser(
            userId=f"u_{user.id}",
            nickname=user.nickname,
            avatarUrl=user.avatar_url,
            status=user.status,
        ),
    )
    return APIResponse(data=response_data)


@router.post("/token/refresh")
async def refresh_token(payload: RefreshTokenRequest) -> APIResponse[RefreshTokenData]:
    try:
        decoded = decode_access_token(payload.refreshToken)
        user_id = int(decoded.get("sub", "0"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc
    if user_id <= 0:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    access_token = create_access_token(user_id)
    return APIResponse(data=RefreshTokenData(accessToken=access_token, expiresIn=7200))

