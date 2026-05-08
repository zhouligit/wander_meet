import asyncio
import logging
import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import bearer_scheme
from app.core.config import get_settings
from app.core.security import create_access_token, decode_access_token, hash_phone
from app.db.session import get_db_session, redis_client
from app.services.auth_blacklist import blacklist_access_jti
from app.services.auth_refresh import issue_refresh_token, rotate_refresh_token, revoke_all_refresh_for_user
from app.services.ihuyi_sms import IhuiSmsError, send_sms_submit_sync
from app.services.ip_rate_limit import enforce_auth_ip_rate_limit
from app.services.phone_validation import parse_cn_mobile
from app.models.user import User
from app.schemas.datetime_iso import datetime_to_rfc3339_utc_z
from app.schemas.auth import (
    LoginUser,
    LogoutData,
    RefreshTokenData,
    RefreshTokenRequest,
    SMSLoginData,
    SMSLoginRequest,
    SendSMSCodeData,
    SendSMSCodeRequest,
)
from app.schemas.common import APIResponse

router = APIRouter(prefix="/auth", tags=["auth"])
SMS_CODE_TTL_SECONDS = 300  # 5 分钟
SMS_SEND_MIN_INTERVAL_SECONDS = 60

logger = logging.getLogger(__name__)


def _generate_sms_code() -> str:
    """6 位数字验证码（100000–999999）。"""
    return str(secrets.randbelow(900000) + 100000)


async def _limit_sms_send_ip(request: Request) -> None:
    await enforce_auth_ip_rate_limit(request, "sms_send")


async def _limit_sms_login_ip(request: Request) -> None:
    await enforce_auth_ip_rate_limit(request, "sms_login")


@router.post("/sms/send", dependencies=[Depends(_limit_sms_send_ip)])
async def send_sms_code(payload: SendSMSCodeRequest) -> APIResponse[SendSMSCodeData]:
    phone = parse_cn_mobile(payload.phone)
    if phone is None:
        raise HTTPException(status_code=400, detail="手机号格式不正确")

    settings = get_settings()
    rate_key = f"wm:sms:send:rate:{phone}"
    acquired = await redis_client.set(
        rate_key,
        "1",
        ex=SMS_SEND_MIN_INTERVAL_SECONDS,
        nx=True,
    )
    if not acquired:
        raise HTTPException(status_code=429, detail="发送过于频繁，请60秒后再试")

    if settings.sms_use_mock:
        code = (settings.sms_mock_code or "123456").strip() or "123456"
        if settings.app_env.lower() in ("prod", "production"):
            logger.warning(
                "SMS_USE_MOCK is on in production — real SMS disabled; phone=%s",
                phone[-4:],
            )
        else:
            logger.info(
                "SMS mock: scene=%s phone=%s (code fixed by SMS_MOCK_CODE)",
                payload.scene,
                phone,
            )
    else:
        code = _generate_sms_code()

    redis_key = f"wm:sms:{payload.scene}:{phone}"
    await redis_client.set(redis_key, code, ex=SMS_CODE_TTL_SECONDS)

    if not settings.sms_use_mock:
        account = (settings.ihuyi_account or "").strip()
        password = (settings.ihuyi_password or "").strip()
        if account and password:
            content = (settings.ihuyi_sms_template or "").replace("{code}", code)
            try:
                await asyncio.to_thread(
                    send_sms_submit_sync,
                    account,
                    password,
                    phone,
                    content,
                )
            except IhuiSmsError as exc:
                await redis_client.delete(redis_key)
                await redis_client.delete(rate_key)
                raise HTTPException(status_code=502, detail=str(exc)) from exc
        else:
            if settings.app_env.lower() in ("prod", "production"):
                await redis_client.delete(redis_key)
                await redis_client.delete(rate_key)
                raise HTTPException(
                    status_code=503,
                    detail="SMS service not configured (set IHUYI_ACCOUNT / IHUYI_PASSWORD)",
                )
            logger.warning(
                "IHUYI not configured — dev code for scene=%s phone=%s code=%s",
                payload.scene,
                phone,
                code,
            )

    return APIResponse(data=SendSMSCodeData(expireInSeconds=SMS_CODE_TTL_SECONDS))


@router.post("/sms/login", dependencies=[Depends(_limit_sms_login_ip)])
async def sms_login(
    payload: SMSLoginRequest, db: AsyncSession = Depends(get_db_session)
) -> APIResponse[SMSLoginData]:
    phone = parse_cn_mobile(payload.phone)
    if phone is None:
        raise HTTPException(status_code=400, detail="手机号格式不正确")

    redis_key = f"wm:sms:login:{phone}"
    cached_code = await redis_client.get(redis_key)
    if not cached_code or cached_code != payload.code:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    await redis_client.delete(redis_key)

    phone_hash = hash_phone(phone)
    user = await db.scalar(select(User).where(User.phone_hash == phone_hash))
    if not user:
        user = User(phone=phone, phone_hash=phone_hash, nickname=f"旅人{phone[-4:]}")
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif not user.phone:
        # Backfill plain phone for historical users after phone column rollout.
        user.phone = phone
        await db.commit()

    settings = get_settings()
    access_token = create_access_token(user.id)
    refresh_raw = await issue_refresh_token(user.id, settings.refresh_token_expires_seconds)

    response_data = SMSLoginData(
        accessToken=access_token,
        expiresIn=settings.access_token_expires_seconds,
        refreshToken=refresh_raw,
        user=LoginUser(
            userId=f"u_{user.id}",
            nickname=user.nickname,
            avatarUrl=user.avatar_url,
            gender=user.gender,
            status=user.status,
            onboardingCompletedAt=datetime_to_rfc3339_utc_z(user.onboarding_completed_at),
        ),
    )
    return APIResponse(data=response_data)


@router.post("/token/refresh")
async def refresh_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db_session),
) -> APIResponse[RefreshTokenData]:
    raw = (payload.refreshToken or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="refreshToken is required")

    settings = get_settings()
    uid, new_rt = await rotate_refresh_token(raw, settings.refresh_token_expires_seconds)
    if uid is None or not new_rt:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = await db.scalar(select(User).where(User.id == uid))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.status == "banned":
        raise HTTPException(status_code=403, detail="User is banned")

    access_token = create_access_token(user.id)
    return APIResponse(
        data=RefreshTokenData(
            accessToken=access_token,
            expiresIn=settings.access_token_expires_seconds,
            refreshToken=new_rt,
        )
    )


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> APIResponse[LogoutData]:
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    user_id = int(payload.get("sub", "0"))
    if user_id <= 0:
        raise HTTPException(status_code=401, detail="Invalid token")

    jti = payload.get("jti")
    exp = payload.get("exp")
    now_ts = int(datetime.now(UTC).timestamp())
    exp_ts = int(exp) if exp is not None else 0
    ttl = max(1, exp_ts - now_ts) if exp_ts > now_ts else 60

    await blacklist_access_jti(jti if isinstance(jti, str) else None, ttl)
    await revoke_all_refresh_for_user(user_id)

    return APIResponse(data=LogoutData())
