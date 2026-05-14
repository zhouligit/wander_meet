"""活动 / 城市大群报名写入（供 activities 与 city_groups 复用）。"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.services.activity_query import to_utc


async def enroll_user_in_activity(
    db: AsyncSession,
    user_id: int,
    activity: Activity,
    *,
    raise_if_already_joined: bool = True,
) -> ActivityEnrollment:
    now_utc = datetime.now(UTC)
    if activity.activity_status != "published":
        raise HTTPException(status_code=400, detail="Activity is not open for enrollment")
    if activity.end_at is not None and to_utc(activity.end_at) <= now_utc:
        raise HTTPException(status_code=400, detail="Activity has ended")

    joined_count = await db.scalar(
        select(func.count(ActivityEnrollment.id)).where(
            ActivityEnrollment.activity_id == activity.id,
            ActivityEnrollment.status == "joined",
        )
    )
    if int(joined_count or 0) >= activity.max_members:
        raise HTTPException(status_code=409, detail="Activity is full")

    existing = await db.scalar(
        select(ActivityEnrollment).where(
            ActivityEnrollment.activity_id == activity.id,
            ActivityEnrollment.user_id == user_id,
        )
    )
    if existing:
        if existing.status == "joined":
            if raise_if_already_joined:
                raise HTTPException(status_code=409, detail="Already enrolled")
            return existing
        existing.status = "joined"
        await db.commit()
        await db.refresh(existing)
        return existing

    enrollment = ActivityEnrollment(
        activity_id=activity.id,
        user_id=user_id,
        status="joined",
    )
    db.add(enrollment)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Already enrolled") from exc
    await db.refresh(enrollment)
    return enrollment
