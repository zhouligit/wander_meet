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
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_douyin_openid,
    hash_phone,
    hash_wechat_openid,
)
from app.db.session import get_db_session, redis_client
from app.services.auth_blacklist import blacklist_access_jti
from app.services.auth_refresh import issue_refresh_token, rotate_refresh_token, revoke_all_refresh_for_user
from app.services.acquisition_source import resolve_new_user_acquisition_source
from app.services.aliyun_sms import AliyunSmsError, send_sms_aliyun_sync
from app.services.ihuyi_sms import IhuiSmsError, send_sms_submit_sync
from app.services.ip_rate_limit import enforce_auth_ip_rate_limit
from app.services.phone_validation import parse_cn_mobile
from app.services.email_auth import (
    authenticate_email_user,
    register_email_user,
    request_email_password_reset,
    reset_email_password,
)
from app.services.douyin_miniapp import DouyinLoginError, code_to_session as douyin_code_to_session
from app.services.wechat_miniapp import WechatLoginError, code_to_session
from app.models.user import User
from app.schemas.datetime_iso import datetime_to_rfc3339_utc_z
from app.schemas.auth import (
    EmailForgotPasswordData,
    EmailForgotPasswordRequest,
    EmailLoginRequest,
    EmailRegisterRequest,
    EmailResetPasswordRequest,
    LoginUser,
    LogoutData,
    RefreshTokenData,
    RefreshTokenRequest,
    SMSLoginData,
    SMSLoginRequest,
    SendSMSCodeData,
    SendSMSCodeRequest,
    WechatLoginRequest,
    DouyinLoginRequest,
)
from app.schemas.common import APIResponse

router = APIRouter(prefix="/auth", tags=["auth"])

logger = logging.getLogger(__name__)


def _generate_sms_code() -> str:
    """6 位数字验证码（100000–999999）。"""
    return str(secrets.randbelow(900000) + 100000)


async def _limit_sms_send_ip(request: Request) -> None:
    await enforce_auth_ip_rate_limit(request, "sms_send")


# 别名：历史上装饰器曾写为 Depends(_limit_sms_send)，未升级的服务器仍会引用该名
_limit_sms_send = _limit_sms_send_ip


async def _limit_sms_login_ip(request: Request) -> None:
    await enforce_auth_ip_rate_limit(request, "sms_login")


async def _limit_wechat_login_ip(request: Request) -> None:
    await enforce_auth_ip_rate_limit(request, "wechat_login")


async def _limit_douyin_login_ip(request: Request) -> None:
    await enforce_auth_ip_rate_limit(request, "douyin_login")


async def _limit_email_register_ip(request: Request) -> None:
    await enforce_auth_ip_rate_limit(request, "email_register")


async def _limit_email_login_ip(request: Request) -> None:
    await enforce_auth_ip_rate_limit(request, "email_login")


async def _limit_email_forgot_ip(request: Request) -> None:
    await enforce_auth_ip_rate_limit(request, "email_forgot")


async def _build_login_response(user: User) -> SMSLoginData:
    settings = get_settings()
    access_token = create_access_token(user.id)
    refresh_raw = await issue_refresh_token(user.id, settings.refresh_token_expires_seconds)
    return SMSLoginData(
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


def _ensure_user_can_login(user: User) -> None:
    if user.status == "banned":
        raise HTTPException(status_code=403, detail="User is banned")
    if user.status == "restricted":
        raise HTTPException(status_code=403, detail="User is restricted")


@router.post("/sms/send", dependencies=[Depends(_limit_sms_send)])
async def send_sms_code(payload: SendSMSCodeRequest) -> APIResponse[SendSMSCodeData]:
    phone = parse_cn_mobile(payload.phone)
    if phone is None:
        raise HTTPException(status_code=400, detail="手机号格式不正确")

    settings = get_settings()
    ttl = max(60, int(settings.sms_code_ttl_seconds))
    send_gap = max(15, int(settings.sms_send_min_interval_seconds))
    rate_key = f"wm:sms:send:rate:{phone}"
    acquired = await redis_client.set(
        rate_key,
        "1",
        ex=send_gap,
        nx=True,
    )
    if not acquired:
        raise HTTPException(
            status_code=429,
            detail=f"发送过于频繁，请{send_gap}秒后再试",
        )

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
    await redis_client.set(redis_key, code, ex=ttl)

    if not settings.sms_use_mock:
        provider = settings.sms_provider
        if provider == "aliyun":
            ak = (settings.aliyun_access_key_id or "").strip()
            sk = (settings.aliyun_access_key_secret or "").strip()
            sign = (settings.aliyun_sms_sign_name or "").strip()
            tpl = (settings.aliyun_sms_template_code or "").strip()
            if ak and sk and sign and tpl:
                endpoint = (settings.aliyun_sms_endpoint or "dysmsapi.aliyuncs.com").strip()
                region = (settings.aliyun_sms_region_id or "cn-hangzhou").strip()
                try:
                    template_param: dict = {"code": code}
                    if settings.aliyun_sms_template_include_minute:
                        template_param["minute"] = str(max(1, ttl // 60))
                    await asyncio.to_thread(
                        send_sms_aliyun_sync,
                        ak,
                        sk,
                        endpoint=endpoint,
                        region_id=region,
                        phone_numbers=phone,
                        sign_name=sign,
                        template_code=tpl,
                        template_param=template_param,
                    )
                except AliyunSmsError as exc:
                    await redis_client.delete(redis_key)
                    await redis_client.delete(rate_key)
                    raise HTTPException(status_code=502, detail=str(exc)) from exc
            else:
                await redis_client.delete(redis_key)
                await redis_client.delete(rate_key)
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Aliyun SMS not configured: set SMS_PROVIDER=aliyun requires "
                        "ALIYUN_ACCESS_KEY_ID, ALIYUN_ACCESS_KEY_SECRET, "
                        "ALIYUN_SMS_SIGN_NAME, ALIYUN_SMS_TEMPLATE_CODE"
                    ),
                )
        else:
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
                await redis_client.delete(redis_key)
                await redis_client.delete(rate_key)
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "互亿无线短信未配置：请使用 SMS_PROVIDER=ihuyi（默认）并设置 "
                        "IHUYI_ACCOUNT、IHUYI_PASSWORD；或改用 SMS_PROVIDER=aliyun 并配置 ALIYUN_*"
                    ),
                )

    return APIResponse(data=SendSMSCodeData(expireInSeconds=ttl))


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
        user = User(
            phone=phone,
            phone_hash=phone_hash,
            nickname=f"旅人{phone[-4:]}",
            acquisition_source=resolve_new_user_acquisition_source(
                payload.acquisitionSource, default=None
            ),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif not user.phone:
        # Backfill plain phone for historical users after phone column rollout.
        user.phone = phone
        await db.commit()

    _ensure_user_can_login(user)
    return APIResponse(data=await _build_login_response(user))


@router.post("/email/register", dependencies=[Depends(_limit_email_register_ip)])
async def email_register(
    payload: EmailRegisterRequest, db: AsyncSession = Depends(get_db_session)
) -> APIResponse[SMSLoginData]:
    """H5 邮箱注册（密码）；成功即签发 token，与短信登录响应一致。"""
    user = await register_email_user(
        db,
        email=payload.email,
        password=payload.password,
        nickname=payload.nickname,
    )
    _ensure_user_can_login(user)
    return APIResponse(data=await _build_login_response(user))


@router.post("/email/login", dependencies=[Depends(_limit_email_login_ip)])
async def email_login(
    payload: EmailLoginRequest, db: AsyncSession = Depends(get_db_session)
) -> APIResponse[SMSLoginData]:
    """H5 邮箱密码登录。"""
    user = await authenticate_email_user(db, email=payload.email, password=payload.password)
    return APIResponse(data=await _build_login_response(user))


@router.post("/email/forgot-password", dependencies=[Depends(_limit_email_forgot_ip)])
async def email_forgot_password(
    payload: EmailForgotPasswordRequest, db: AsyncSession = Depends(get_db_session)
) -> APIResponse[EmailForgotPasswordData]:
    """
    忘记密码：向已注册的邮箱密码账号发送 6 位验证码。
    无论邮箱是否存在，均返回成功（防枚举）。
    """
    ttl = await request_email_password_reset(db, email=payload.email)
    return APIResponse(data=EmailForgotPasswordData(expireInSeconds=ttl))


@router.post("/email/reset-password", dependencies=[Depends(_limit_email_forgot_ip)])
async def email_reset_password(
    payload: EmailResetPasswordRequest, db: AsyncSession = Depends(get_db_session)
) -> APIResponse[SMSLoginData]:
    """校验邮件验证码并重置密码；成功签发新 token，并吊销该用户全部 refresh。"""
    user = await reset_email_password(
        db,
        email=payload.email,
        code=payload.code,
        new_password=payload.newPassword,
    )
    _ensure_user_can_login(user)
    return APIResponse(data=await _build_login_response(user))


@router.post("/wechat/login", dependencies=[Depends(_limit_wechat_login_ip)])
async def wechat_login(
    payload: WechatLoginRequest, db: AsyncSession = Depends(get_db_session)
) -> APIResponse[SMSLoginData]:
    """微信小程序 ``wx.login`` 的 code 换 openid 并签发 token（响应与短信登录一致）。"""
    try:
        session = await code_to_session(payload.code)
    except WechatLoginError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    openid = session.openid
    user = await db.scalar(select(User).where(User.mp_openid == openid))
    if not user:
        phone_hash = hash_wechat_openid(openid)
        suffix = openid[-4:] if len(openid) >= 4 else openid
        user = User(
            phone=None,
            phone_hash=phone_hash,
            mp_openid=openid,
            mp_unionid=session.unionid,
            nickname=f"旅人{suffix}",
            acquisition_source=resolve_new_user_acquisition_source(
                payload.acquisitionSource, default="mp_weixin"
            ),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info("wechat_login_new_user user_id=%s openid_suffix=%s", user.id, suffix)
    else:
        if session.unionid and not user.mp_unionid:
            user.mp_unionid = session.unionid
            await db.commit()

    _ensure_user_can_login(user)
    return APIResponse(data=await _build_login_response(user))


@router.post("/douyin/login", dependencies=[Depends(_limit_douyin_login_ip)])
async def douyin_login(
    payload: DouyinLoginRequest, db: AsyncSession = Depends(get_db_session)
) -> APIResponse[SMSLoginData]:
    """抖音小程序 ``tt.login`` 的 code 换 openid 并签发 token（响应与短信/微信登录一致）。"""
    try:
        session = await douyin_code_to_session(payload.code)
    except DouyinLoginError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    openid = session.openid
    user = await db.scalar(select(User).where(User.dy_openid == openid))
    if not user:
        phone_hash = hash_douyin_openid(openid)
        suffix = openid[-4:] if len(openid) >= 4 else openid
        user = User(
            phone=None,
            phone_hash=phone_hash,
            dy_openid=openid,
            nickname=f"旅人{suffix}",
            acquisition_source=resolve_new_user_acquisition_source(
                payload.acquisitionSource, default="mp_douyin"
            ),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info("douyin_login_new_user user_id=%s openid_suffix=%s", user.id, suffix)
    else:
        await db.commit()

    _ensure_user_can_login(user)
    return APIResponse(data=await _build_login_response(user))


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
