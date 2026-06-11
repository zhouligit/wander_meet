"""Shared helpers for activity-scoped direct messages (pair threads, membership, blocks)."""

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.dm_thread import DmThread
from app.models.user_block import UserBlock


def sort_user_pair(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


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


async def get_thread_by_users(db: AsyncSession, u1: int, u2: int) -> DmThread | None:
    low, high = sort_user_pair(u1, u2)
    return await db.scalar(
        select(DmThread).where(DmThread.user_low_id == low, DmThread.user_high_id == high)
    )


async def list_dm_peer_user_ids(db: AsyncSession, user_id: int) -> list[int]:
    """私信会话对端 user id（与「好友列表」一致：已建立 dm thread）。"""
    rows = (
        await db.execute(
            select(DmThread.user_low_id, DmThread.user_high_id).where(
                or_(DmThread.user_low_id == user_id, DmThread.user_high_id == user_id)
            )
        )
    ).all()
    peer_ids: set[int] = set()
    for low, high in rows:
        peer_ids.add(int(high if int(low) == user_id else low))
    return sorted(peer_ids)
