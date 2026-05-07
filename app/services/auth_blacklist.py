"""Access JWT ``jti`` 黑名单（登出后至 token 自然过期）。"""

from __future__ import annotations

from app.db.session import redis_client

BL_PREFIX = "wm:auth:bl:"


async def blacklist_access_jti(jti: str | None, ttl_seconds: int) -> None:
    if not jti or ttl_seconds <= 0:
        return
    await redis_client.set(f"{BL_PREFIX}{jti}", "1", ex=int(ttl_seconds))


async def is_jti_blacklisted(jti: str | None) -> bool:
    if not jti:
        return False
    return bool(await redis_client.exists(f"{BL_PREFIX}{jti}"))
