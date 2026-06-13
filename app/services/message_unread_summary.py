"""底部 Tab / 消息中心：未读汇总（群聊 + 私聊 + 系统通知）。"""

from __future__ import annotations

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.direct_message import DirectMessage
from app.models.dm_thread import DmThread
from app.models.dm_thread_read import DmThreadRead
from app.models.notification import Notification
from app.models.user_chat_read import UserChatRead
from app.services.platform_notification import DM_NOTIFICATION_TYPES
from app.services.chat_unread import get_chat_unread_counts


async def sum_group_chat_unread(db: AsyncSession, user_id: int) -> int:
    activities = (
        (
            await db.execute(
                select(Activity)
                .join(ActivityEnrollment, ActivityEnrollment.activity_id == Activity.id)
                .where(
                    ActivityEnrollment.user_id == user_id,
                    ActivityEnrollment.status == "joined",
                )
            )
        )
        .scalars()
        .all()
    )
    if not activities:
        return 0

    activity_ids = [a.id for a in activities]
    read_rows = await db.execute(
        select(UserChatRead.activity_id, UserChatRead.last_read_message_id).where(
            UserChatRead.user_id == user_id,
            UserChatRead.activity_id.in_(activity_ids),
        )
    )
    read_map = {int(aid): int(last or 0) for aid, last in read_rows.all()}
    unread_map = await get_chat_unread_counts(db, user_id, list(activities), read_map)
    return sum(int(v) for v in unread_map.values())


async def sum_direct_chat_unread(db: AsyncSession, user_id: int) -> int:
    thread_filter = or_(DmThread.user_low_id == user_id, DmThread.user_high_id == user_id)
    cnt = await db.scalar(
        select(func.count(DirectMessage.id))
        .select_from(DirectMessage)
        .join(DmThread, DirectMessage.thread_id == DmThread.id)
        .outerjoin(
            DmThreadRead,
            and_(
                DmThreadRead.thread_id == DirectMessage.thread_id,
                DmThreadRead.user_id == user_id,
            ),
        )
        .where(
            thread_filter,
            DirectMessage.sender_id != user_id,
            DirectMessage.id > func.coalesce(DmThreadRead.last_read_message_id, 0),
        )
    )
    return int(cnt or 0)


async def count_unread_notifications(db: AsyncSession, user_id: int) -> int:
    cnt = await db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
            Notification.type.notin_(DM_NOTIFICATION_TYPES),
        )
    )
    return int(cnt or 0)


async def build_message_unread_summary(db: AsyncSession, user_id: int) -> tuple[int, int]:
    """返回 ``(chatUnread, notifUnread)``；chatUnread = 活动群 + 私聊。"""
    group_unread = await sum_group_chat_unread(db, user_id)
    dm_unread = await sum_direct_chat_unread(db, user_id)
    notif_unread = await count_unread_notifications(db, user_id)
    return group_unread + dm_unread, notif_unread
