"""用户鉴权行与 /me 读缓存（Redis）。"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import redis_client
from app.models.user import User
from app.schemas.me import MeData, MyStatsData

logger = logging.getLogger(__name__)

USER_AUTH_PREFIX = "wm:user:auth:"
ME_DATA_PREFIX = "wm:cache:me:"
ME_STATS_PREFIX = "wm:cache:me:stats:"

_DATETIME_FIELDS = frozenset(
    {"stay_end_at", "onboarding_completed_at", "created_at", "updated_at"}
)


def _auth_cache_active() -> bool:
    s = get_settings()
    return s.cache_user_auth_enabled and s.cache_user_auth_ttl_seconds > 0


def _me_cache_active() -> bool:
    s = get_settings()
    return s.cache_me_enabled and s.cache_me_ttl_seconds > 0


def _encode_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _decode_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def user_to_cache_dict(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "phone": user.phone,
        "phone_hash": user.phone_hash,
        "mp_openid": user.mp_openid,
        "mp_unionid": user.mp_unionid,
        "email": user.email,
        "password_hash": user.password_hash,
        "nickname": user.nickname,
        "gender": user.gender,
        "avatar_url": user.avatar_url,
        "bio": user.bio,
        "tags": user.tags,
        "country_code": user.country_code,
        "traveler_roles": user.traveler_roles,
        "current_place": user.current_place,
        "stay_kind": user.stay_kind,
        "stay_end_at": _encode_dt(user.stay_end_at),
        "acquisition_source": user.acquisition_source,
        "notify_prefs": user.notify_prefs,
        "show_distance": user.show_distance,
        "onboarding_completed_at": _encode_dt(user.onboarding_completed_at),
        "status": user.status,
        "role": user.role,
        "created_at": _encode_dt(user.created_at),
        "updated_at": _encode_dt(user.updated_at),
    }


def user_from_cache_dict(data: dict[str, Any]) -> User:
    user = User()
    for key, value in data.items():
        if key in _DATETIME_FIELDS:
            value = _decode_dt(value) if isinstance(value, str) else value
        setattr(user, key, value)
    return user


async def get_cached_user(user_id: int) -> User | None:
    if not _auth_cache_active():
        return None
    raw = await redis_client.get(f"{USER_AUTH_PREFIX}{user_id}")
    if not raw:
        return None
    try:
        return user_from_cache_dict(json.loads(raw))
    except Exception:
        logger.warning("user_auth_cache_decode_failed user_id=%s", user_id, exc_info=True)
        await redis_client.delete(f"{USER_AUTH_PREFIX}{user_id}")
        return None


async def set_cached_user(user: User) -> None:
    if not _auth_cache_active():
        return
    settings = get_settings()
    await redis_client.set(
        f"{USER_AUTH_PREFIX}{user.id}",
        json.dumps(user_to_cache_dict(user), ensure_ascii=False),
        ex=settings.cache_user_auth_ttl_seconds,
    )


async def load_user_for_auth(db: AsyncSession, user_id: int) -> User | None:
    cached = await get_cached_user(user_id)
    if cached is not None:
        return cached
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is not None:
        await set_cached_user(user)
    return user


async def load_user_for_update(db: AsyncSession, user_id: int) -> User | None:
    """写操作专用：始终从 DB 加载并绑定当前 session。

    勿对 ``load_user_for_auth`` 返回的缓存副本做 ``commit`` / ``refresh``。
    """
    return await db.get(User, user_id)


async def invalidate_user_cache(user_id: int) -> None:
    await redis_client.delete(
        f"{USER_AUTH_PREFIX}{user_id}",
        f"{ME_DATA_PREFIX}{user_id}",
        f"{ME_STATS_PREFIX}{user_id}",
    )


async def invalidate_me_stats(user_id: int) -> None:
    await redis_client.delete(f"{ME_STATS_PREFIX}{user_id}")


async def get_cached_me_data(user_id: int) -> MeData | None:
    if not _me_cache_active():
        return None
    raw = await redis_client.get(f"{ME_DATA_PREFIX}{user_id}")
    if not raw:
        return None
    try:
        return MeData.model_validate_json(raw)
    except Exception:
        logger.warning("me_cache_decode_failed user_id=%s", user_id, exc_info=True)
        await redis_client.delete(f"{ME_DATA_PREFIX}{user_id}")
        return None


async def set_cached_me_data(user_id: int, data: MeData) -> None:
    if not _me_cache_active():
        return
    settings = get_settings()
    await redis_client.set(
        f"{ME_DATA_PREFIX}{user_id}",
        data.model_dump_json(),
        ex=settings.cache_me_ttl_seconds,
    )


async def get_cached_me_stats(user_id: int) -> MyStatsData | None:
    if not _me_cache_active():
        return None
    raw = await redis_client.get(f"{ME_STATS_PREFIX}{user_id}")
    if not raw:
        return None
    try:
        return MyStatsData.model_validate_json(raw)
    except Exception:
        logger.warning("me_stats_cache_decode_failed user_id=%s", user_id, exc_info=True)
        await redis_client.delete(f"{ME_STATS_PREFIX}{user_id}")
        return None


async def set_cached_me_stats(user_id: int, data: MyStatsData) -> None:
    if not _me_cache_active():
        return
    settings = get_settings()
    await redis_client.set(
        f"{ME_STATS_PREFIX}{user_id}",
        data.model_dump_json(),
        ex=settings.cache_me_ttl_seconds,
    )
