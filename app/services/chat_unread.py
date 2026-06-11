"""活动群聊未读数：普通活动 Redis 计数；城群 bounded COUNT（避免大表扫描）。"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import redis_client
from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.activity_message import ActivityMessage
from app.models.user_chat_read import UserChatRead
from app.services.city_hall import is_city_hall_activity

logger = logging.getLogger(__name__)

UNREAD_PREFIX = "wm:unread:"
CHAT_UNREAD_SCAN_CAP = 100
CITY_HALL_UNREAD_DISPLAY_CAP = 99
CHAT_MESSAGE_COUNT_QUERY_CAP = 100
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


def parse_activity_pk(activity_id: str) -> int:
    s = str(activity_id or "")
    if s.startswith("act_"):
        s = s[4:]
    return int(s) if s.isdigit() else 0


async def capped_message_count(
    db: AsyncSession,
    activity_id: int,
    *,
    cap: int = CHAT_MESSAGE_COUNT_QUERY_CAP,
) -> int:
    """最多数 ``cap`` 条消息；返回 ``cap`` 表示至少 ``cap`` 条（前端展示 99+）。"""
    subq = (
        select(ActivityMessage.id)
        .where(ActivityMessage.activity_id == activity_id)
        .limit(cap)
        .subquery()
    )
    n = (await db.execute(select(func.count()).select_from(subq))).scalar_one()
    return int(n or 0)


async def get_message_counts(
    db: AsyncSession,
    activity_ids: list[int],
) -> dict[int, int]:
    if not activity_ids:
        return {}
    rows = await db.execute(
        select(ActivityMessage.activity_id, func.count(ActivityMessage.id))
        .where(ActivityMessage.activity_id.in_(activity_ids))
        .group_by(ActivityMessage.activity_id)
    )
    return {int(aid): int(cnt) for aid, cnt in rows.all()}


async def get_chat_stats_for_activity(
    db: AsyncSession,
    activity: Activity,
    *,
    user_id: int | None,
    joined: bool,
    use_capped_total: bool = False,
) -> tuple[int, int | None]:
    """返回 ``(messageCount, unreadCount|None)``。"""
    if use_capped_total:
        message_count = await capped_message_count(db, activity.id)
    else:
        counts = await get_message_counts(db, [activity.id])
        message_count = counts.get(activity.id, 0)

    unread_count: int | None = None
    if user_id and joined:
        read_row = await db.scalar(
            select(UserChatRead.last_read_message_id).where(
                UserChatRead.user_id == user_id,
                UserChatRead.activity_id == activity.id,
            )
        )
        read_map = {activity.id: int(read_row or 0)}
        unread_map = await get_chat_unread_counts(db, user_id, [activity], read_map)
        unread_count = int(unread_map.get(activity.id, 0))
    return message_count, unread_count


async def enrich_activity_cards_chat_stats(
    db: AsyncSession,
    user_id: int | None,
    cards: list,
) -> list:
    """为活动卡片批量附加 ``messageCount`` / ``unreadCount``（原地 model_copy）。"""
    from app.schemas.activity import ActivityCard

    if not cards:
        return cards

    activity_ids = [parse_activity_pk(c.activityId) for c in cards]
    activity_ids = [aid for aid in activity_ids if aid > 0]
    if not activity_ids:
        return cards

    msg_counts = await get_message_counts(db, activity_ids)

    joined_ids = [
        parse_activity_pk(c.activityId)
        for c in cards
        if c.enrollmentStatus == "joined" and parse_activity_pk(c.activityId) > 0
    ]
    unread_map: dict[int, int] = {}
    if user_id and joined_ids:
        act_rows = await db.execute(select(Activity).where(Activity.id.in_(joined_ids)))
        joined_activities = list(act_rows.scalars().all())
        if joined_activities:
            read_rows = await db.execute(
                select(UserChatRead.activity_id, UserChatRead.last_read_message_id).where(
                    UserChatRead.user_id == user_id,
                    UserChatRead.activity_id.in_(joined_ids),
                )
            )
            read_map = {int(aid): int(last or 0) for aid, last in read_rows.all()}
            unread_map = await get_chat_unread_counts(
                db, user_id, joined_activities, read_map
            )

    enriched: list[ActivityCard] = []
    for card in cards:
        aid = parse_activity_pk(card.activityId)
        joined = card.enrollmentStatus == "joined"
        enriched.append(
            card.model_copy(
                update={
                    "messageCount": msg_counts.get(aid, 0),
                    "unreadCount": unread_map.get(aid, 0) if user_id and joined else None,
                }
            )
        )
    return enriched
