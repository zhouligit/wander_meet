"""活动群聊未读数：普通活动 Redis 计数；城群 bounded COUNT（避免大表扫描）。"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import redis_client
from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.activity_message import ActivityMessage
from app.services.city_hall import is_city_hall_activity

logger = logging.getLogger(__name__)

UNREAD_PREFIX = "wm:unread:"
CHAT_UNREAD_SCAN_CAP = 100
CITY_HALL_UNREAD_DISPLAY_CAP = 99
# 超过该报名数不在发消息时 Redis INCR 扩散（城群走 bounded COUNT）
REDIS_UNREAD_FANOUT_MAX_MEMBERS = 500
UNREAD_REDIS_TTL_SECONDS = 86400 * 7


def unread_redis_key(user_id: int, activity_id: int) -> str:
    return f"{UNREAD_PREFIX}{user_id}:{activity_id}"


async def reset_chat_unread(user_id: int, activity_id: int) -> None:
    await redis_client.set(
        unread_redis_key(user_id, activity_id),
        "0",
        ex=UNREAD_REDIS_TTL_SECONDS,
    )


async def increment_chat_unread_for_message(
    db: AsyncSession,
    activity: Activity,
    sender_id: int,
) -> None:
    """新消息后给除发送者外的成员 +1（城群与超大活动跳过 Redis 扩散）。"""
    if is_city_hall_activity(activity):
        return

    member_count = await db.scalar(
        select(func.count(ActivityEnrollment.id)).where(
            ActivityEnrollment.activity_id == activity.id,
            ActivityEnrollment.status == "joined",
        )
    )
    if int(member_count or 0) > REDIS_UNREAD_FANOUT_MAX_MEMBERS:
        return

    rows = await db.execute(
        select(ActivityEnrollment.user_id).where(
            ActivityEnrollment.activity_id == activity.id,
            ActivityEnrollment.status == "joined",
            ActivityEnrollment.user_id != sender_id,
        )
    )
    user_ids = [int(r[0]) for r in rows.all()]
    if not user_ids:
        return

    pipe = redis_client.pipeline()
    for uid in user_ids:
        key = unread_redis_key(uid, activity.id)
        pipe.incr(key)
        pipe.expire(key, UNREAD_REDIS_TTL_SECONDS)
    await pipe.execute()


async def bounded_unread_count(
    db: AsyncSession,
    activity_id: int,
    last_read_message_id: int,
    *,
    scan_cap: int = CHAT_UNREAD_SCAN_CAP,
) -> int:
    """最多扫描 ``scan_cap`` 条消息行，用于城群或未命中 Redis 时的降级。"""
    subq = (
        select(ActivityMessage.id)
        .where(
            ActivityMessage.activity_id == activity_id,
            ActivityMessage.id > last_read_message_id,
        )
        .limit(scan_cap)
        .subquery()
    )
    n = (await db.execute(select(func.count()).select_from(subq))).scalar_one()
    return int(n or 0)


async def get_chat_unread_counts(
    db: AsyncSession,
    user_id: int,
    activities: list[Activity],
    read_map: dict[int, int],
) -> dict[int, int]:
    """返回 ``activity_id -> unreadCount``。"""
    if not activities:
        return {}

    result: dict[int, int] = {}
    redis_aids: list[int] = []
    redis_keys: list[str] = []
    city_hall_aids: list[int] = []
    redis_miss_aids: list[int] = []

    for activity in activities:
        if is_city_hall_activity(activity):
            city_hall_aids.append(activity.id)
        else:
            redis_aids.append(activity.id)
            redis_keys.append(unread_redis_key(user_id, activity.id))

    if redis_keys:
        vals = await redis_client.mget(redis_keys)
        for aid, val in zip(redis_aids, vals, strict=True):
            if val is not None:
                result[aid] = max(0, int(val))
            else:
                redis_miss_aids.append(aid)

    for aid in city_hall_aids:
        last_read = read_map.get(aid, 0)
        cnt = await bounded_unread_count(db, aid, last_read)
        result[aid] = min(CITY_HALL_UNREAD_DISPLAY_CAP, cnt)

    for aid in redis_miss_aids:
        last_read = read_map.get(aid, 0)
        cnt = await bounded_unread_count(db, aid, last_read)
        result[aid] = cnt
        await redis_client.set(
            unread_redis_key(user_id, aid),
            str(cnt),
            ex=UNREAD_REDIS_TTL_SECONDS,
        )

    return result
