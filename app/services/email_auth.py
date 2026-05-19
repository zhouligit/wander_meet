"""H5 邮箱 + 密码注册、登录与忘记密码。"""

from __future__ import annotations

import asyncio
import logging
import secrets

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_email
from app.db.session import redis_client
from app.models.user import User
from app.services.email_validation import nickname_from_email, parse_email
from app.services.email_send import EmailSendError, send_email_sync
from app.services.password_policy import hash_password, validate_password, verify_password
from app.services.auth_refresh import revoke_all_refresh_for_user

logger = logging.getLogger(__name__)

_FAIL_PREFIX = "wm:auth:email_fail:"
_LOCK_PREFIX = "wm:auth:email_lock:"
_REGISTER_RATE_PREFIX = "wm:email:register:rate:"
_FORGOT_RATE_PREFIX = "wm:email:forgot:rate:"
_RESET_CODE_PREFIX = "wm:email:reset:"


def user_has_email_account(user: User) -> bool:
    return bool((user.email or "").strip() and (user.password_hash or "").strip())


async def enforce_email_register_rate(email: str) -> None:
    settings = get_settings()
    gap = max(15, int(settings.auth_email_register_min_interval_seconds))
    key = f"{_REGISTER_RATE_PREFIX}{email}"
    acquired = await redis_client.set(key, "1", ex=gap, nx=True)
    if not acquired:
        raise HTTPException(
            status_code=429,
            detail=f"注册过于频繁，请{gap}秒后再试",
        )


async def _ensure_not_locked(email: str) -> None:
    if await redis_client.get(f"{_LOCK_PREFIX}{email}"):
        settings = get_settings()
        raise HTTPException(
            status_code=429,
            detail=f"登录失败次数过多，请{settings.auth_email_login_lock_seconds // 60}分钟后再试",
        )


async def _record_login_failure(email: str) -> None:
    settings = get_settings()
    max_fail = max(1, settings.auth_email_login_max_failures)
    lock_sec = max(60, settings.auth_email_login_lock_seconds)
    key = f"{_FAIL_PREFIX}{email}"
    n = await redis_client.incr(key)
    if n == 1:
        await redis_client.expire(key, lock_sec)
    if n >= max_fail:
        await redis_client.set(f"{_LOCK_PREFIX}{email}", "1", ex=lock_sec)
        await redis_client.delete(key)


async def _clear_login_failures(email: str) -> None:
    await redis_client.delete(f"{_FAIL_PREFIX}{email}")
    await redis_client.delete(f"{_LOCK_PREFIX}{email}")


async def find_user_by_email(db: AsyncSession, email: str) -> User | None:
    eh = hash_email(email)
    return await db.scalar(
        select(User).where(or_(User.email == email, User.phone_hash == eh))
    )


async def register_email_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    nickname: str | None,
) -> User:
    normalized = parse_email(email)
    if normalized is None:
        raise HTTPException(status_code=400, detail="邮箱格式不正确")

    pwd_err = validate_password(password)
    if pwd_err:
        raise HTTPException(status_code=400, detail=pwd_err)

    await enforce_email_register_rate(normalized)

    existing = await find_user_by_email(db, normalized)
    if existing and user_has_email_account(existing):
        raise HTTPException(status_code=409, detail="邮箱已注册")

    nick = (nickname or "").strip()[:32] or nickname_from_email(normalized)
    user = User(
        email=normalized,
        phone=None,
        phone_hash=hash_email(normalized),
        password_hash=hash_password(password),
        nickname=nick,
        acquisition_source="h5_email",
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="邮箱已注册") from exc
    await db.refresh(user)
    logger.info("email_register user_id=%s email_suffix=%s", user.id, normalized.split("@")[-1])
    return user


async def authenticate_email_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
) -> User:
    normalized = parse_email(email)
    if normalized is None:
        raise HTTPException(status_code=400, detail="邮箱格式不正确")

    await _ensure_not_locked(normalized)

    user = await find_user_by_email(db, normalized)
    if not user or not user_has_email_account(user):
        await _record_login_failure(normalized)
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    if not verify_password(password, user.password_hash or ""):
        await _record_login_failure(normalized)
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    if user.status == "banned":
        raise HTTPException(status_code=403, detail="User is banned")
    if user.status == "restricted":
        raise HTTPException(status_code=403, detail="User is restricted")

    await _clear_login_failures(normalized)
    if not user.email:
        user.email = normalized
        await db.commit()
    return user


def _generate_reset_code() -> str:
    return str(secrets.randbelow(900000) + 100000)


async def request_email_password_reset(db: AsyncSession, *, email: str) -> int:
    """
    发送重置密码验证码。无论邮箱是否存在，对调用方均视为成功（防枚举）。
    返回验证码有效秒数。
    """
    settings = get_settings()
    normalized = parse_email(email)
    if normalized is None:
        raise HTTPException(status_code=400, detail="邮箱格式不正确")

    ttl = max(60, int(settings.auth_email_reset_code_ttl_seconds))
    gap = max(15, int(settings.auth_email_forgot_min_interval_seconds))
    rate_key = f"{_FORGOT_RATE_PREFIX}{normalized}"
    acquired = await redis_client.set(rate_key, "1", ex=gap, nx=True)
    if not acquired:
        raise HTTPException(
            status_code=429,
            detail=f"发送过于频繁，请{gap}秒后再试",
        )

    user = await find_user_by_email(db, normalized)
    if user and user_has_email_account(user):
        if settings.email_use_mock:
            if settings.app_env.lower() in ("prod", "production"):
                logger.warning(
                    "EMAIL_USE_MOCK is on in production — reset emails not sent; email_suffix=%s",
                    normalized.split("@")[-1],
                )
            code = (settings.email_mock_code or "123456").strip() or "123456"
        else:
            code = _generate_reset_code()
        await redis_client.set(f"{_RESET_CODE_PREFIX}{normalized}", code, ex=ttl)
        minutes = max(1, ttl // 60)
        body = settings.email_reset_body_template.format(code=code, minutes=minutes)
        try:
            await asyncio.to_thread(
                send_email_sync,
                to=normalized,
                subject=settings.email_reset_subject,
                body=body,
            )
        except EmailSendError as exc:
            await redis_client.delete(f"{_RESET_CODE_PREFIX}{normalized}")
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        logger.info("email_reset_sent user_id=%s", user.id)

    return ttl


async def reset_email_password(
    db: AsyncSession,
    *,
    email: str,
    code: str,
    new_password: str,
) -> User:
    normalized = parse_email(email)
    if normalized is None:
        raise HTTPException(status_code=400, detail="邮箱格式不正确")

    pwd_err = validate_password(new_password)
    if pwd_err:
        raise HTTPException(status_code=400, detail=pwd_err)

    raw_code = (code or "").strip()
    if not raw_code:
        raise HTTPException(status_code=400, detail="验证码不能为空")

    redis_key = f"{_RESET_CODE_PREFIX}{normalized}"
    cached = await redis_client.get(redis_key)
    if not cached or cached != raw_code:
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    user = await find_user_by_email(db, normalized)
    if not user or not user_has_email_account(user):
        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    if user.status == "banned":
        raise HTTPException(status_code=403, detail="User is banned")
    if user.status == "restricted":
        raise HTTPException(status_code=403, detail="User is restricted")

    user.password_hash = hash_password(new_password)
    if not user.email:
        user.email = normalized
    await db.commit()
    await db.refresh(user)

    await redis_client.delete(redis_key)
    await _clear_login_failures(normalized)
    await revoke_all_refresh_for_user(user.id)
    logger.info("email_password_reset user_id=%s", user.id)
    return user
