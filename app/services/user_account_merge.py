"""将微信临时账号合并到已有手机号账号（迁移外键后删除来源用户）。"""

from __future__ import annotations

import logging

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.activity_message import ActivityMessage
from app.models.direct_message import DirectMessage
from app.models.dm_request import DmRequest
from app.models.dm_thread import DmThread
from app.models.dm_thread_read import DmThreadRead
from app.models.notification import Notification
from app.models.place_activity_alert import PlaceActivityAlert
from app.models.report import Report
from app.models.user import User
from app.services.email_auth import user_has_email_account
from app.models.user_block import UserBlock
from app.models.user_chat_read import UserChatRead
from app.models.user_feedback import UserFeedback
from app.models.user_verification import UserVerification

logger = logging.getLogger(__name__)


def _dm_pair(low: int, high: int) -> tuple[int, int]:
    return (low, high) if low <= high else (high, low)


async def _merge_activity_enrollments(
    db: AsyncSession, *, from_user_id: int, to_user_id: int
) -> None:
    from_enrs = (
        await db.execute(
            select(ActivityEnrollment).where(ActivityEnrollment.user_id == from_user_id)
        )
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


async def _merge_user_chat_reads(
    db: AsyncSession, *, from_user_id: int, to_user_id: int
) -> None:
    rows = (
        await db.execute(select(UserChatRead).where(UserChatRead.user_id == from_user_id))
    ).scalars().all()
    for row in rows:
        clash = await db.scalar(
            select(UserChatRead.id).where(
                UserChatRead.user_id == to_user_id,
                UserChatRead.activity_id == row.activity_id,
            )
        )
        if clash:
            await db.delete(row)
        else:
            row.user_id = to_user_id


async def _merge_dm_thread_reads(
    db: AsyncSession, *, from_user_id: int, to_user_id: int
) -> None:
    rows = (
        await db.execute(select(DmThreadRead).where(DmThreadRead.user_id == from_user_id))
    ).scalars().all()
    for row in rows:
        clash = await db.scalar(
            select(DmThreadRead.id).where(
                DmThreadRead.user_id == to_user_id,
                DmThreadRead.thread_id == row.thread_id,
            )
        )
        if clash:
            await db.delete(row)
        else:
            row.user_id = to_user_id


async def _merge_place_activity_alerts(
    db: AsyncSession, *, from_user_id: int, to_user_id: int
) -> None:
    rows = (
        await db.execute(
            select(PlaceActivityAlert).where(PlaceActivityAlert.user_id == from_user_id)
        )
    ).scalars().all()
    for row in rows:
        clash = await db.scalar(
            select(PlaceActivityAlert.id).where(
                PlaceActivityAlert.user_id == to_user_id,
                PlaceActivityAlert.city_code == row.city_code,
                PlaceActivityAlert.category_id == row.category_id,
                PlaceActivityAlert.date_range == row.date_range,
            )
        )
        if clash:
            await db.delete(row)
        else:
            row.user_id = to_user_id


async def _merge_dm_threads(
    db: AsyncSession, *, from_user_id: int, to_user_id: int
) -> None:
    threads = (
        await db.execute(
            select(DmThread).where(
                or_(
                    DmThread.user_low_id == from_user_id,
                    DmThread.user_high_id == from_user_id,
                )
            )
        )
    ).scalars().all()
    seen: set[int] = set()
    for thread in threads:
        if thread.id in seen:
            continue
        seen.add(thread.id)

        low = to_user_id if thread.user_low_id == from_user_id else thread.user_low_id
        high = to_user_id if thread.user_high_id == from_user_id else thread.user_high_id
        new_low, new_high = _dm_pair(low, high)

        if new_low == new_high:
            await db.execute(delete(DmThreadRead).where(DmThreadRead.thread_id == thread.id))
            await db.execute(delete(DirectMessage).where(DirectMessage.thread_id == thread.id))
            await db.delete(thread)
            continue

        existing = await db.scalar(
            select(DmThread).where(
                DmThread.user_low_id == new_low,
                DmThread.user_high_id == new_high,
                DmThread.id != thread.id,
            )
        )
        if existing:
            await db.execute(
                update(DirectMessage)
                .where(DirectMessage.thread_id == thread.id)
                .values(thread_id=existing.id)
            )
            from_reads = (
                await db.execute(
                    select(DmThreadRead).where(DmThreadRead.thread_id == thread.id)
                )
            ).scalars().all()
            for read in from_reads:
                clash = await db.scalar(
                    select(DmThreadRead.id).where(
                        DmThreadRead.user_id == read.user_id,
                        DmThreadRead.thread_id == existing.id,
                    )
                )
                if clash:
                    await db.delete(read)
                else:
                    read.thread_id = existing.id
            await db.delete(thread)
        else:
            thread.user_low_id = new_low
            thread.user_high_id = new_high


async def merge_user_into(db: AsyncSession, *, from_user_id: int, to_user_id: int) -> None:
    """把 ``from_user_id`` 的业务数据并入 ``to_user_id``，最后删除 ``from_user`` 行。"""
    if from_user_id == to_user_id:
        return

    from_user = await db.scalar(select(User).where(User.id == from_user_id))
    to_user = await db.scalar(select(User).where(User.id == to_user_id))
    if not from_user or not to_user:
        raise ValueError("merge users not found")

    await _merge_activity_enrollments(db, from_user_id=from_user_id, to_user_id=to_user_id)

    await db.execute(
        update(Activity).where(Activity.organizer_id == from_user_id).values(organizer_id=to_user_id)
    )
    await db.execute(
        update(ActivityMessage)
        .where(ActivityMessage.sender_id == from_user_id)
        .values(sender_id=to_user_id)
    )
    await db.execute(
        update(DirectMessage)
        .where(DirectMessage.sender_id == from_user_id)
        .values(sender_id=to_user_id)
    )

    await _merge_place_activity_alerts(db, from_user_id=from_user_id, to_user_id=to_user_id)
    await _merge_user_chat_reads(db, from_user_id=from_user_id, to_user_id=to_user_id)

    await db.execute(
        update(UserFeedback).where(UserFeedback.user_id == from_user_id).values(user_id=to_user_id)
    )

    await _merge_dm_thread_reads(db, from_user_id=from_user_id, to_user_id=to_user_id)

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
        update(Report).where(Report.reporter_id == from_user_id).values(reporter_id=to_user_id)
    )
    await db.execute(
        update(UserBlock).where(UserBlock.blocker_id == from_user_id).values(blocker_id=to_user_id)
    )
    await db.execute(
        update(UserBlock).where(UserBlock.blocked_id == from_user_id).values(blocked_id=to_user_id)
    )

    await _merge_dm_threads(db, from_user_id=from_user_id, to_user_id=to_user_id)

    if user_has_email_account(from_user):
        from_email = (from_user.email or "").strip().lower()
        if user_has_email_account(to_user):
            to_email = (to_user.email or "").strip().lower()
            if from_email and to_email and from_email != to_email:
                raise ValueError("合并失败：两个账号绑定了不同邮箱")
        elif from_email:
            to_user.email = from_email
            to_user.password_hash = from_user.password_hash
        from_user.email = None
        from_user.password_hash = None

    if from_user.mp_openid and not to_user.mp_openid:
        to_user.mp_openid = from_user.mp_openid
        from_user.mp_openid = None
    if from_user.mp_unionid and not to_user.mp_unionid:
        to_user.mp_unionid = from_user.mp_unionid

    await db.flush()
    await db.delete(from_user)
    await db.flush()
    logger.info("user_merge from_id=%s to_id=%s", from_user_id, to_user_id)
