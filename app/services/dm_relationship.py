"""Shared helpers for activity-scoped direct messages (pair threads, membership, blocks)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.dm_thread import DmThread
from app.models.dm_thread_removal import DmThreadRemoval
from app.models.user_block import UserBlock


def sort_user_pair(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def peer_user_id(thread: DmThread, user_id: int) -> int:
    if thread.user_low_id == user_id:
        return int(thread.user_high_id)
    if thread.user_high_id == user_id:
        return int(thread.user_low_id)
    raise ValueError("user is not a thread participant")


async def is_activity_participant(
    db: AsyncSession, activity_id: int, user_id: int
) -> bool:
    act = await db.scalar(select(Activity).where(Activity.id == activity_id))
    if not act:
        return False
    if act.organizer_id == user_id:
        return True
    en = await db.scalar(
        select(ActivityEnrollment).where(
            ActivityEnrollment.activity_id == activity_id,
            ActivityEnrollment.user_id == user_id,
            ActivityEnrollment.status == "joined",
        )
    )
    return en is not None


async def either_blocked(db: AsyncSession, a: int, b: int) -> bool:
    row = await db.scalar(
        select(UserBlock).where(
            or_(
                and_(UserBlock.blocker_id == a, UserBlock.blocked_id == b),
                and_(UserBlock.blocker_id == b, UserBlock.blocked_id == a),
            )
        )
    )
    return row is not None


async def get_blocked_peer_ids(db: AsyncSession, user_id: int) -> set[int]:
    rows = (
        await db.execute(
            select(UserBlock.blocked_id).where(UserBlock.blocker_id == user_id)
        )
    ).scalars().all()
    rows2 = (
        await db.execute(
            select(UserBlock.blocker_id).where(UserBlock.blocked_id == user_id)
        )
    ).scalars().all()
    return {int(x) for x in rows} | {int(x) for x in rows2}


async def get_thread_by_users(db: AsyncSession, u1: int, u2: int) -> DmThread | None:
    low, high = sort_user_pair(u1, u2)
    return await db.scalar(
        select(DmThread).where(DmThread.user_low_id == low, DmThread.user_high_id == high)
    )


async def user_removed_thread(
    db: AsyncSession, user_id: int, thread_id: int
) -> bool:
    row = await db.scalar(
        select(DmThreadRemoval.id).where(
            DmThreadRemoval.user_id == user_id,
            DmThreadRemoval.thread_id == thread_id,
        )
    )
    return row is not None


async def remove_thread_for_user(
    db: AsyncSession, user_id: int, thread: DmThread
) -> None:
    existing = await db.scalar(
        select(DmThreadRemoval).where(
            DmThreadRemoval.user_id == user_id,
            DmThreadRemoval.thread_id == thread.id,
        )
    )
    if existing:
        existing.removed_at = datetime.now(UTC)
        return
    db.add(DmThreadRemoval(user_id=user_id, thread_id=thread.id))


async def clear_thread_removals(db: AsyncSession, thread_id: int) -> None:
    await db.execute(delete(DmThreadRemoval).where(DmThreadRemoval.thread_id == thread_id))


async def is_thread_visible_for_user(
    db: AsyncSession, user_id: int, thread: DmThread
) -> bool:
    if user_id not in (thread.user_low_id, thread.user_high_id):
        return False
    if await user_removed_thread(db, user_id, thread.id):
        return False
    peer = peer_user_id(thread, user_id)
    if await either_blocked(db, user_id, peer):
        return False
    return True


def visible_thread_filter(user_id: int):
    """SQL filter: thread belongs to user, not removed by user, peer not blocked."""
    blocked_ids_subq = (
        select(UserBlock.blocked_id.label("pid"))
        .where(UserBlock.blocker_id == user_id)
        .union(
            select(UserBlock.blocker_id.label("pid")).where(
                UserBlock.blocked_id == user_id
            )
        )
        .subquery()
    )
    removed_subq = select(DmThreadRemoval.thread_id).where(
        DmThreadRemoval.user_id == user_id
    )
    membership = or_(DmThread.user_low_id == user_id, DmThread.user_high_id == user_id)
    peer_not_blocked = or_(
        and_(
            DmThread.user_low_id == user_id,
            ~DmThread.user_high_id.in_(select(blocked_ids_subq.c.pid)),
        ),
        and_(
            DmThread.user_high_id == user_id,
            ~DmThread.user_low_id.in_(select(blocked_ids_subq.c.pid)),
        ),
    )
    return and_(
        membership,
        peer_not_blocked,
        ~DmThread.id.in_(removed_subq),
    )


async def list_dm_peer_user_ids(db: AsyncSession, user_id: int) -> list[int]:
    """私信会话对端 user id（与「好友列表」一致：已建立 dm thread 且未删除/未拉黑）。"""
    filt = visible_thread_filter(user_id)
    rows = (
        await db.execute(select(DmThread.user_low_id, DmThread.user_high_id).where(filt))
    ).all()
    peer_ids: set[int] = set()
    for low, high in rows:
        peer_ids.add(int(high if int(low) == user_id else low))
    return sorted(peer_ids)


async def user_considers_peer_connected(
    db: AsyncSession, user_id: int, peer_id: int
) -> bool:
    """当前用户是否仍将对方视为好友（有 thread 且未单方面删除）。"""
    thread = await get_thread_by_users(db, user_id, peer_id)
    if not thread:
        return False
    if await user_removed_thread(db, user_id, thread.id):
        return False
    if await either_blocked(db, user_id, peer_id):
        return False
    return True
