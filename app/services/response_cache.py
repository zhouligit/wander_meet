"""读多写少接口的 Redis 短缓存（活动列表 / 附近 / 详情）。"""

from __future__ import annotations

import logging

from app.core.config import get_settings
from app.db.session import redis_client
from app.schemas.activity import ActivityDetailData, ActivityListData, NearbyActivityListData

logger = logging.getLogger(__name__)

ACTIVITY_LIST_PREFIX = "wm:cache:act:list:"
ACTIVITY_NEARBY_PREFIX = "wm:cache:act:nearby:"
ACTIVITY_DETAIL_PREFIX = "wm:cache:act:detail:"


def activity_list_cache_key(
    city_code: str,
    date_range: str,
    category_id: str | None,
    page: int,
    page_size: int,
    sort_by: str = "startAt",
) -> str:
    cat = (category_id or "").strip() or "_"
    sb = (sort_by or "startAt").strip() or "startAt"
    return f"{ACTIVITY_LIST_PREFIX}{city_code}:{date_range}:{cat}:{sb}:{page}:{page_size}"


def activity_nearby_cache_key(
    *,
    city_code: str | None,
    date_range: str,
    category_id: str | None,
    sort_by: str,
    lat: float,
    lng: float,
    radius_km: float,
    page: int,
    page_size: int,
) -> str:
    city = (city_code or "").strip() or "_"
    cat = (category_id or "").strip() or "_"
    lat_r = round(lat, 3)
    lng_r = round(lng, 3)
    radius_r = round(radius_km, 1)
    return (
        f"{ACTIVITY_NEARBY_PREFIX}{city}:{date_range}:{cat}:{sort_by}:"
        f"{lat_r}:{lng_r}:{radius_r}:{page}:{page_size}"
    )


def activity_detail_cache_key(activity_id: int) -> str:
    return f"{ACTIVITY_DETAIL_PREFIX}{activity_id}"


def _read_cache_active() -> bool:
    settings = get_settings()
    return settings.cache_activity_list_enabled and settings.cache_activity_list_ttl_seconds > 0


def _cache_ttl() -> int:
    return get_settings().cache_activity_list_ttl_seconds


async def _scan_delete(pattern: str) -> int:
    deleted = 0
    async for key in redis_client.scan_iter(match=pattern, count=200):
        await redis_client.delete(key)
        deleted += 1
    return deleted


async def get_cached_activity_list(key: str) -> ActivityListData | None:
    if not _read_cache_active():
        return None
    raw = await redis_client.get(key)
    if not raw:
        return None
    try:
        return ActivityListData.model_validate_json(raw)
    except Exception:
        logger.warning("activity_list_cache_decode_failed key=%s", key, exc_info=True)
        await redis_client.delete(key)
        return None


async def set_cached_activity_list(key: str, data: ActivityListData) -> None:
    if not _read_cache_active():
        return
    await redis_client.set(key, data.model_dump_json(), ex=_cache_ttl())


async def get_cached_activity_nearby(key: str) -> NearbyActivityListData | None:
    if not _read_cache_active():
        return None
    raw = await redis_client.get(key)
    if not raw:
        return None
    try:
        return NearbyActivityListData.model_validate_json(raw)
    except Exception:
        logger.warning("activity_nearby_cache_decode_failed key=%s", key, exc_info=True)
        await redis_client.delete(key)
        return None


async def set_cached_activity_nearby(key: str, data: NearbyActivityListData) -> None:
    if not _read_cache_active():
        return
    await redis_client.set(key, data.model_dump_json(), ex=_cache_ttl())


async def get_cached_activity_detail(activity_id: int) -> ActivityDetailData | None:
    if not _read_cache_active():
        return None
    raw = await redis_client.get(activity_detail_cache_key(activity_id))
    if not raw:
        return None
    try:
        return ActivityDetailData.model_validate_json(raw)
    except Exception:
        logger.warning(
            "activity_detail_cache_decode_failed activity_id=%s",
            activity_id,
            exc_info=True,
        )
        await redis_client.delete(activity_detail_cache_key(activity_id))
        return None


async def set_cached_activity_detail(activity_id: int, data: ActivityDetailData) -> None:
    if not _read_cache_active():
        return
    await redis_client.set(
        activity_detail_cache_key(activity_id),
        data.model_dump_json(),
        ex=_cache_ttl(),
    )


async def invalidate_activity_detail(activity_id: int) -> None:
    await redis_client.delete(activity_detail_cache_key(activity_id))


async def invalidate_activity_list_for_city(city_code: str) -> None:
    """发布/变更等活动写操作后，清除该城市下的同城列表缓存。"""
    cc = (city_code or "").strip()
    if not cc:
        return
    deleted = await _scan_delete(f"{ACTIVITY_LIST_PREFIX}{cc}:*")
    if deleted:
        logger.debug("activity_list_cache_invalidated city=%s keys=%s", cc, deleted)


async def invalidate_activity_nearby_for_city(city_code: str | None) -> None:
    cc = (city_code or "").strip() or "_"
    deleted = await _scan_delete(f"{ACTIVITY_NEARBY_PREFIX}{cc}:*")
    if deleted:
        logger.debug("activity_nearby_cache_invalidated city=%s keys=%s", cc, deleted)


async def invalidate_activity_read_caches(
    *,
    city_code: str | None = None,
    activity_id: int | None = None,
) -> None:
    """写操作后失效列表 / 附近 / 详情缓存。"""
    if city_code is not None:
        cc = (city_code or "").strip()
        if cc:
            await invalidate_activity_list_for_city(cc)
            await invalidate_activity_nearby_for_city(cc)
        await invalidate_activity_nearby_for_city(None)
    if activity_id is not None:
        await invalidate_activity_detail(activity_id)
