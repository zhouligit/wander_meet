"""将微信临时账号合并到已有手机号账号（迁移外键后删除来源用户）。"""

from __future__ import annotations

import logging

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.activity_message import ActivityMessage
from app.models.dm_request import DmRequest
from app.models.dm_thread import DmThread
from app.models.dm_thread_read import DmThreadRead
from app.models.notification import Notification
from app.models.place_activity_alert import PlaceActivityAlert
from app.models.user import User
from app.models.user_block import UserBlock
from app.models.user_chat_read import UserChatRead
from app.models.user_feedback import UserFeedback
from app.models.user_verification import UserVerification

logger = logging.getLogger(__name__)


async def merge_user_into(db: AsyncSession, *, from_user_id: int, to_user_id: int) -> None:
    """把 ``from_user_id`` 的业务数据并入 ``to_user_id``，最后删除 ``from_user`` 行。"""
    if from_user_id == to_user_id:
        return

    from_user = await db.scalar(select(User).where(User.id == from_user_id))
    to_user = await db.scalar(select(User).where(User.id == to_user_id))
    if not from_user or not to_user:
        raise ValueError("merge users not found")

    from_enrs = (
        await db.execute(select(ActivityEnrollment).where(ActivityEnrollment.user_id == from_user_id))
    ).scalars().all()
    for enr in from_enrs:
        clash = await db.scalar(
            select(ActivityEnrollment.id).where(
                ActivityEnrollment.activity_id == enr.activity_id,
                ActivityEnrollment.user_id == to_user_id,
            )
        )
        if clash:
            await db.delete(enr)
        else:
            enr.user_id = to_user_id

    await db.execute(
        update(Activity).where(Activity.organizer_id == from_user_id).values(organizer_id=to_user_id)
    )
    await db.execute(
        update(ActivityMessage)
        .where(ActivityMessage.sender_id == from_user_id)
        .values(sender_id=to_user_id)
    )
    await db.execute(
        update(PlaceActivityAlert)
        .where(PlaceActivityAlert.user_id == from_user_id)
        .values(user_id=to_user_id)
    )
    await db.execute(
        update(UserFeedback).where(UserFeedback.user_id == from_user_id).values(user_id=to_user_id)
    )
    await db.execute(
        update(UserChatRead).where(UserChatRead.user_id == from_user_id).values(user_id=to_user_id)
    )
    await db.execute(
        update(DmThreadRead).where(DmThreadRead.user_id == from_user_id).values(user_id=to_user_id)
    )
    await db.execute(
        update(DmRequest)
        .where(DmRequest.from_user_id == from_user_id)
        .values(from_user_id=to_user_id)
    )
    await db.execute(
        update(DmRequest).where(DmRequest.to_user_id == from_user_id).values(to_user_id=to_user_id)
    )
    await db.execute(
        update(Notification).where(Notification.user_id == from_user_id).values(user_id=to_user_id)
    )
    await db.execute(
        update(UserVerification)
        .where(UserVerification.user_id == from_user_id)
        .values(user_id=to_user_id)
    )
    await db.execute(
        update(UserBlock).where(UserBlock.blocker_id == from_user_id).values(blocker_id=to_user_id)
    )
    await db.execute(
        update(UserBlock).where(UserBlock.blocked_id == from_user_id).values(blocked_id=to_user_id)
    )
    await db.execute(
        update(DmThread)
        .where(DmThread.user_low_id == from_user_id)
        .values(user_low_id=to_user_id)
    )
    await db.execute(
        update(DmThread)
        .where(DmThread.user_high_id == from_user_id)
        .values(user_high_id=to_user_id)
    )

    if from_user.mp_openid and not to_user.mp_openid:
        to_user.mp_openid = from_user.mp_openid
        from_user.mp_openid = None
    if from_user.mp_unionid and not to_user.mp_unionid:
        to_user.mp_unionid = from_user.mp_unionid

    await db.flush()
    await db.delete(from_user)
    await db.flush()
    logger.info("user_merge from_id=%s to_id=%s", from_user_id, to_user_id)
