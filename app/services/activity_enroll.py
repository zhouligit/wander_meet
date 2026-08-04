"""活动 / 城市大群报名写入（供 activities 与 city_groups 复用）。"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.user import User
from app.services.activity_query import to_utc
from app.services.enrollment_identity import (
    apply_enrollment_identity,
    normalize_enroll_identity_payload,
)


async def enroll_user_in_activity(
    db: AsyncSession,
    user_id: int,
    activity: Activity,
    user: User | None = None,
    *,
    participant_name: str | None = None,
    id_card_number: str | None = None,
    raise_if_already_joined: bool = True,
) -> ActivityEnrollment:
    now_utc = datetime.now(UTC)
    if activity.activity_status != "published":
        raise HTTPException(status_code=400, detail="Activity is not open for enrollment")
    if activity.end_at is not None and to_utc(activity.end_at) <= now_utc:
        raise HTTPException(status_code=400, detail="Activity has ended")

    if user is None:
        user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    require_identity = bool(activity.require_enrollment_identity)
    norm_name, norm_id = normalize_enroll_identity_payload(
        participant_name,
        id_card_number,
        required=require_identity,
    )

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
        if norm_name and norm_id:
            apply_enrollment_identity(existing, user, norm_name, norm_id)
        await db.flush()
        await db.refresh(existing)
        return existing

    enrollment = ActivityEnrollment(
        activity_id=activity.id,
        user_id=user_id,
        status="joined",
    )
    if norm_name and norm_id:
        apply_enrollment_identity(enrollment, user, norm_name, norm_id)
    db.add(enrollment)
    await db.flush()
    await db.refresh(enrollment)
    return enrollment
