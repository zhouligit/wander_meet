"""Opaque refresh token（Redis）；单用户仅保留最近一次会话的 refresh。"""

from __future__ import annotations

import secrets

from app.db.session import redis_client

REFRESH_PREFIX = "wm:rt:"
USER_REFRESH_PREFIX = "wm:rt:user:"


async def issue_refresh_token(user_id: int, ttl_seconds: int) -> str:
    """签发新的 refresh，并吊销该用户此前保留的 refresh。"""
    old = await redis_client.get(f"{USER_REFRESH_PREFIX}{user_id}")
    if old:
        await redis_client.delete(f"{REFRESH_PREFIX}{old}")
    raw = secrets.token_urlsafe(32)
    await redis_client.set(f"{REFRESH_PREFIX}{raw}", str(user_id), ex=ttl_seconds)
    await redis_client.set(f"{USER_REFRESH_PREFIX}{user_id}", raw, ex=ttl_seconds)
    return raw


async def validate_refresh_token(raw: str) -> int | None:
    """若 refresh 有效则返回 user_id，否则 ``None``。"""
    uid_s = await redis_client.get(f"{REFRESH_PREFIX}{raw}")
    if not uid_s:
        return None
    try:
        return int(uid_s)
    except ValueError:
        return None


async def rotate_refresh_token(old_raw: str, ttl_seconds: int) -> tuple[int | None, str | None]:
    """用旧 refresh 轮换为新 refresh；无效则 ``(None, None)``。"""
    uid = await validate_refresh_token(old_raw)
    if uid is None:
        return None, None
    new_raw = await issue_refresh_token(uid, ttl_seconds)
    return uid, new_raw


async def revoke_all_refresh_for_user(user_id: int) -> None:
    """登出或封号：吊销该用户 refresh。"""
    raw = await redis_client.get(f"{USER_REFRESH_PREFIX}{user_id}")
    if raw:
        await redis_client.delete(f"{REFRESH_PREFIX}{raw}")
    await redis_client.delete(f"{USER_REFRESH_PREFIX}{user_id}")
