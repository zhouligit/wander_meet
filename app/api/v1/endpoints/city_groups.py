"""城市大群：lookup / join；会话与消息复用 ``/activities/act_*``。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_optional_user
from app.db.session import get_db_session
from app.models.activity import Activity
from app.models.activity_enrollment import ActivityEnrollment
from app.models.user import User
from app.schemas.city_group import CityHallJoinData, CityHallJoinRequest, CityHallLookupData
from app.schemas.common import APIResponse
from app.services.activity_enroll import enroll_user_in_activity
from app.services.city_hall import (
    CITY_HALL_ACTIVITY_KIND,
    get_or_create_city_hall_activity,
    is_city_hall_activity,
    normalize_city_code,
)

router = APIRouter(prefix="/city-groups", tags=["city-groups"])
logger = logging.getLogger(__name__)


async def _member_count(db: AsyncSession, activity_id: int) -> int:
    return int(
        await db.scalar(
            select(func.count(ActivityEnrollment.id)).where(
                ActivityEnrollment.activity_id == activity_id,
                ActivityEnrollment.status == "joined",
            )
        )
        or 0
    )


@router.get("/lookup")
async def lookup_city_hall(
    request: Request,
    cityCode: str = Query(..., min_length=1, max_length=32),
    db: AsyncSession = Depends(get_db_session),
    optional_user: User | None = Depends(get_optional_user),
) -> APIResponse[CityHallLookupData]:
    try:
        cc = normalize_city_code(cityCode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid cityCode") from exc

    if optional_user:
        request.state.user_id = optional_user.id

    row = await db.scalar(
        select(Activity).where(
            Activity.activity_kind == CITY_HALL_ACTIVITY_KIND,
            Activity.city_hall_city_code == cc,
        )
    )
    if not row:
        return APIResponse(
            data=CityHallLookupData(
                exists=False,
                cityCode=cc,
                displayName="",
                memberCount=0,
                joined=False if optional_user else None,
                activityId=None,
                activityKind="event",
            )
        )

    cnt = await _member_count(db, row.id)
    joined: bool | None = None
    if optional_user:
        en = await db.scalar(
            select(ActivityEnrollment).where(
                ActivityEnrollment.activity_id == row.id,
                ActivityEnrollment.user_id == optional_user.id,
                ActivityEnrollment.status == "joined",
            )
        )
        joined = en is not None

    return APIResponse(
        data=CityHallLookupData(
            exists=True,
            cityCode=cc,
            displayName=row.title,
            memberCount=cnt,
            joined=joined,
            activityId=f"act_{row.id}",
            activityKind="city_hall",
        )
    )


@router.post("/join")
async def join_city_hall(
    request: Request,
    payload: CityHallJoinRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> APIResponse[CityHallJoinData]:
    if current_user.status != "active":
        raise HTTPException(status_code=403, detail="User is restricted")
    try:
        cc = normalize_city_code(payload.cityCode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid cityCode") from exc

    activity = await get_or_create_city_hall_activity(
        db, cc, log_user_id=current_user.id
    )
    if not is_city_hall_activity(activity):
        raise HTTPException(status_code=500, detail="invalid city hall state")

    enrollment = await enroll_user_in_activity(
        db, current_user.id, activity, raise_if_already_joined=False
    )
    cnt = await _member_count(db, activity.id)

    logger.info(
        "city_hall_join user_id=%s request_id=%s activity_id=%s city=%s",
        current_user.id,
        getattr(request.state, "request_id", ""),
        activity.id,
        cc,
    )

    return APIResponse(
        data=CityHallJoinData(
            cityCode=cc,
            displayName=activity.title,
            memberCount=cnt,
            joined=True,
            activityId=f"act_{activity.id}",
            enrollmentId=f"enr_{enrollment.id}",
        )
    )
